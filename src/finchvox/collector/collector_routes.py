"""
Collector routes for audio chunk uploads, logs, and exceptions.

This module provides route registration functions for the collector endpoints,
which handle data ingestion from LiveKit Agents and Pipecat applications.
"""

import json
import re
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse, Response
from loguru import logger

from finchvox.body_limit import limit_latest_route_body

from .audio_handler import AudioHandler, RecordingInUseError, RecordingTooLargeError
from .config import (
    ALLOWED_AUDIO_FORMATS,
    ALLOWED_FINAL_AUDIO_FORMATS,
    MAX_AUDIO_FILE_SIZE,
    MAX_FINAL_AUDIO_FILE_SIZE,
    MAX_JSON_BODY_BYTES,
    UPLOAD_BODY_MARGIN_BYTES,
    get_session_dir,
)

# What request.json() raises for a bad body. Catching only these matters: the body
# limit's 413 is also raised through request.json() and must not become a 400.
_INVALID_JSON_ERRORS = (ValueError, RecursionError)


def _otel_attributes(span: dict) -> dict[str, object]:
    """Decode the small subset of OTLP JSON attributes needed for correlation."""
    decoded: dict[str, object] = {}
    for attr in span.get("attributes", []) or []:
        key = attr.get("key")
        value = attr.get("value") or {}
        if not key:
            continue
        for value_key in (
            "string_value",
            "int_value",
            "double_value",
            "bool_value",
        ):
            if value_key in value:
                decoded[key] = value[value_key]
                break
    return decoded


def _livekit_report_identity(report: dict) -> tuple[str | None, str | None, str | None]:
    """Return (job_id, room_id, room_name) across Python/JS report spellings."""
    job_id = report.get("job_id") or report.get("jobId")
    room_id = report.get("room_id") or report.get("roomId")
    room_name = report.get("room") or report.get("room_name") or report.get("roomName")
    return (
        str(job_id) if job_id else None,
        str(room_id) if room_id else None,
        str(room_name) if room_name else None,
    )


def _resolve_livekit_trace_id(data_dir: Path, report: dict) -> str | None:
    """Find the local OTel trace that belongs to a LiveKit SessionReport.

    LiveKit's report does not currently include the OTel trace ID, but its job,
    room SID, and room name are also emitted on LiveKit spans. Matching these
    values lets a normal ``on_session_end`` callback attach the report/audio
    without application code manually carrying a trace ID through the session.
    """
    job_id, room_id, room_name = _livekit_report_identity(report)
    if not any((job_id, room_id, room_name)):
        return None

    sessions_dir = data_dir / "sessions"
    if not sessions_dir.exists():
        return None

    best: tuple[int, float, str] | None = None
    for session_dir in sessions_dir.iterdir():
        if not session_dir.is_dir() or not re.match(r"^[a-f0-9]{32}$", session_dir.name):
            continue
        trace_file = session_dir / f"trace_{session_dir.name}.jsonl"
        if not trace_file.exists():
            continue
        score = 0
        try:
            with trace_file.open() as handle:
                for line in handle:
                    if not line.strip():
                        continue
                    try:
                        span = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    attrs = _otel_attributes(span)
                    span_job_id = attrs.get("job_id") or attrs.get("lk.job_id")
                    span_room_id = attrs.get("room_id") or attrs.get("lk.room_sid") or attrs.get("lk.room_id")
                    if job_id and str(span_job_id or "") == job_id:
                        score = max(score, 100)
                    if room_id and str(span_room_id or "") == room_id:
                        score = max(score, 70)
                    span_room_name = attrs.get("lk.pii.room_name") or attrs.get("lk.room_name")
                    if room_name and str(span_room_name or "") == room_name:
                        score = max(score, 40)
                    if score >= 100:
                        break
        except OSError:
            continue

        if score:
            candidate = (score, trace_file.stat().st_mtime, session_dir.name)
            if best is None or candidate > best:
                best = candidate

    return best[2] if best else None


def _store_livekit_report(data_dir: Path, trace_id: str, report: dict) -> Path:
    session_dir = get_session_dir(data_dir, trace_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    destination = session_dir / "livekit_report.json"
    destination.write_text(json.dumps(report, indent=2))
    return destination


def register_collector_routes(
    app: FastAPI, audio_handler: AudioHandler, prefix: str = "/collector"
):
    """
    Register collector routes on an existing FastAPI app with URL prefix.

    Args:
        app: Existing FastAPI application to register routes on
        audio_handler: AudioHandler instance for managing audio storage
        prefix: URL prefix for all collector routes (default: "/collector")
    """

    @app.post(f"{prefix}/audio/{{trace_id}}/chunk")
    async def upload_audio_chunk(
        trace_id: str,
        audio: Annotated[UploadFile, File(description="Audio file (WAV format)")],
        metadata: Annotated[str, Form(description="JSON metadata string")],
    ):
        """
        Upload audio chunk for a trace.

        Args:
            trace_id: Hex string trace ID (32 chars)
            audio: Audio file (WAV format)
            metadata: JSON string with:
                - chunk_number: int
                - timestamp: ISO format string
                - sample_rate: int
                - num_channels: int
                - timing_events: list[dict] (optional)

        Returns:
            JSON response with storage path and status

        Raises:
            HTTPException: For validation errors or server errors
        """
        try:
            # Validate trace_id format
            if len(trace_id) != 32 or not all(
                c in "0123456789abcdef" for c in trace_id
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid trace_id format: must be 32 hex chars, got {trace_id}",
                )

            # Parse metadata
            try:
                metadata_dict = json.loads(metadata)
            except json.JSONDecodeError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON metadata: {e}",
                )

            # Validate required metadata fields
            required_fields = [
                "chunk_number",
                "timestamp",
                "sample_rate",
                "num_channels",
            ]
            missing = [f for f in required_fields if f not in metadata_dict]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing required metadata fields: {missing}",
                )

            # Read audio data
            audio_data = await audio.read()

            # Validate file size
            if len(audio_data) > MAX_AUDIO_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail=f"Audio file too large: {len(audio_data)} bytes (max {MAX_AUDIO_FILE_SIZE})",
                )

            # Validate file format (basic check)
            file_ext = Path(audio.filename or "unknown.wav").suffix.lower()
            if file_ext not in ALLOWED_AUDIO_FORMATS:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported audio format: {file_ext} (allowed: {ALLOWED_AUDIO_FORMATS})",
                )

            # Check if this is a new trace or existing trace (for logging)
            existing_chunks = audio_handler.list_chunks(trace_id)
            is_new_trace = len(existing_chunks) == 0

            if is_new_trace:
                logger.info(
                    f"New audio trace {trace_id[:8]}... - receiving chunk #{metadata_dict['chunk_number']}"
                )
            else:
                logger.info(
                    f"Audio trace {trace_id[:8]}... - receiving chunk #{metadata_dict['chunk_number']} (total: {len(existing_chunks) + 1})"
                )

            # Save audio chunk
            saved_path = await audio_handler.save_audio_chunk(
                trace_id=trace_id,
                chunk_number=metadata_dict["chunk_number"],
                audio_data=audio_data,
                metadata=metadata_dict,
            )

            if saved_path is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to save audio chunk",
                )

            return JSONResponse(
                status_code=status.HTTP_201_CREATED,
                content={
                    "status": "success",
                    "trace_id": trace_id,
                    "chunk_number": metadata_dict["chunk_number"],
                    "file_path": str(saved_path),
                    "size_bytes": len(audio_data),
                },
            )

        except HTTPException:
            raise
        except (OSError, KeyError, TypeError, ValueError) as e:
            logger.exception(
                f"Failed to process audio upload for trace {trace_id}: {e}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Internal server error processing audio upload",
            )

    limit_latest_route_body(app, MAX_AUDIO_FILE_SIZE + UPLOAD_BODY_MARGIN_BYTES)

    @app.post(f"{prefix}/livekit/report")
    async def receive_livekit_report_auto(request: Request):
        """Resolve a SessionReport to its local trace using LiveKit identifiers."""
        try:
            report = await request.json()
        except _INVALID_JSON_ERRORS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
            )
        if not isinstance(report, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="SessionReport must be a JSON object",
            )

        trace_id = _resolve_livekit_trace_id(audio_handler.data_dir, report)
        if not trace_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    "No matching LiveKit trace found. Flush traces first, or upload "
                    "to /collector/livekit/{trace_id}/report with an explicit trace ID."
                ),
            )

        _store_livekit_report(audio_handler.data_dir, trace_id, report)
        logger.info(
            f"Resolved LiveKit SessionReport to trace {trace_id[:8]}..."
        )
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"status": "success", "trace_id": trace_id},
        )

    limit_latest_route_body(app, MAX_JSON_BODY_BYTES)

    @app.post(f"{prefix}/livekit/{{trace_id}}/report")
    async def receive_livekit_report(trace_id: str, request: Request):
        """Store a local LiveKit SessionReport beside the matching OTel trace."""
        if not re.match(r"^[a-f0-9]{32}$", trace_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trace_id format"
            )
        try:
            report = await request.json()
        except _INVALID_JSON_ERRORS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON"
            )

        _store_livekit_report(audio_handler.data_dir, trace_id, report)
        logger.info(f"Received LiveKit SessionReport for {trace_id[:8]}...")
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={"status": "success", "trace_id": trace_id},
        )

    limit_latest_route_body(app, MAX_JSON_BODY_BYTES)

    @app.post(f"{prefix}/livekit/{{trace_id}}/audio")
    async def receive_livekit_audio(
        trace_id: str,
        audio: Annotated[UploadFile, File(description="Finalized session recording")],
    ):
        """Store a finalized LiveKit recording for synchronized local replay."""
        if not re.match(r"^[a-f0-9]{32}$", trace_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid trace_id format"
            )
        extension = Path(audio.filename or "audio.wav").suffix.lower() or ".wav"
        if extension not in ALLOWED_FINAL_AUDIO_FORMATS:
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    f"Unsupported finalized audio format: {extension} "
                    f"(allowed: {ALLOWED_FINAL_AUDIO_FORMATS})"
                ),
            )

        try:
            total = await audio_handler.save_final_recording(
                trace_id, audio, extension, MAX_FINAL_AUDIO_FILE_SIZE
            )
        except RecordingTooLargeError as e:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=str(e)
            ) from e
        except RecordingInUseError as e:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail=str(e)
            ) from e

        logger.info(f"Received LiveKit audio for {trace_id[:8]}... ({total} bytes)")
        return JSONResponse(
            status_code=status.HTTP_201_CREATED,
            content={
                "status": "success",
                "trace_id": trace_id,
                "size_bytes": total,
                "format": extension[1:],
            },
        )

    limit_latest_route_body(app, MAX_FINAL_AUDIO_FILE_SIZE + UPLOAD_BODY_MARGIN_BYTES)

    @app.get(f"{prefix}/health")
    async def health_check():
        """
        Health check endpoint for monitoring.

        Returns:
            Status information
        """
        return {"status": "healthy", "service": "finchvox-collector"}

    @app.get(f"{prefix}/audio/{{trace_id}}/chunks")
    async def list_audio_chunks(trace_id: str):
        """
        List all audio chunks for a trace.

        Args:
            trace_id: OpenTelemetry trace ID

        Returns:
            JSON with list of chunks

        Raises:
            HTTPException: If listing fails
        """
        try:
            chunks = audio_handler.list_chunks(trace_id)
            return {
                "trace_id": trace_id,
                "chunk_count": len(chunks),
                "chunks": [{"path": str(p), "name": p.name} for p in chunks],
            }
        except OSError as e:
            logger.error(f"Failed to list chunks for trace {trace_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to list audio chunks",
            )

    @app.post(f"{prefix}/environment/{{trace_id}}")
    async def receive_environment(trace_id: str, request: Request):
        if not re.match(r"^[a-f0-9]{32}$", trace_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid trace_id format",
            )

        try:
            env_data = await request.json()
        except _INVALID_JSON_ERRORS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid JSON",
            )

        session_dir = get_session_dir(audio_handler.data_dir, trace_id)
        session_dir.mkdir(parents=True, exist_ok=True)

        env_file = session_dir / f"environment_{trace_id}.json"
        env_file.write_text(json.dumps(env_data, indent=2))

        logger.info(f"Received environment data for trace {trace_id[:8]}...")

        return Response(status_code=status.HTTP_201_CREATED)

    limit_latest_route_body(app, MAX_JSON_BODY_BYTES)
