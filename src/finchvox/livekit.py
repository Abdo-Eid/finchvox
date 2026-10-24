"""Small helpers for local LiveKit session artifacts.

OpenTelemetry is the primary path. These helpers are optional: they let an app
attach LiveKit's locally-generated SessionReport and a finalized audio recording
to the same Finchvox session so the replay UI can be fully synchronized.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiohttp
from opentelemetry import trace as otel_trace


def current_trace_id() -> str | None:
    """Return the active OpenTelemetry trace ID as 32 lowercase hex characters."""
    span_context = otel_trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")


def _report_to_dict(report: Any) -> dict[str, Any]:
    if report is None:
        return {}
    if isinstance(report, dict):
        return report
    if hasattr(report, "to_dict"):
        value = report.to_dict()
        if isinstance(value, dict):
            return value
    if hasattr(report, "model_dump"):
        value = report.model_dump(mode="json")
        if isinstance(value, dict):
            return value
    raise TypeError("report must be a dict or expose to_dict()/model_dump()")


async def upload_session_artifacts(
    trace_id: str | None = None,
    *,
    report: Any | None = None,
    audio_path: str | Path | None = None,
    endpoint: str = "http://localhost:3000",
) -> str:
    """Attach a LiveKit SessionReport and/or recording to a Finchvox trace.

    ``trace_id`` is optional when ``report`` is provided. In that common path,
    Finchvox resolves the report to the matching local trace using LiveKit's
    job ID, room SID, or room name. This makes an ``on_session_end`` callback
    enough for a complete local replay without carrying OTel context manually.

    Args:
        trace_id: Optional 32-character OpenTelemetry trace ID used by Finchvox.
        report: A LiveKit ``SessionReport`` (or its dictionary form).
        audio_path: Optional finalized local recording. If omitted and ``report``
            contains ``audio_recording_path``, that path is used automatically.
        endpoint: Finchvox HTTP server origin.

    Returns:
        The resolved 32-character Finchvox/OpenTelemetry trace ID.
    """
    if trace_id is not None and (
        len(trace_id) != 32 or any(ch not in "0123456789abcdef" for ch in trace_id)
    ):
        raise ValueError("trace_id must be 32 lowercase hexadecimal characters")

    base = endpoint.rstrip("/")
    report_dict = _report_to_dict(report) if report is not None else None
    if trace_id is None and report_dict is None:
        raise ValueError("report is required when trace_id is not provided")
    if audio_path is None and report_dict:
        audio_path = report_dict.get("audio_recording_path") or report_dict.get(
            "audioRecordingPath"
        )

    async with aiohttp.ClientSession() as session:
        if report_dict is not None:
            report_url = (
                f"{base}/collector/livekit/{trace_id}/report"
                if trace_id
                else f"{base}/collector/livekit/report"
            )
            async with session.post(report_url, json=report_dict) as response:
                response.raise_for_status()
                if trace_id is None:
                    payload = await response.json()
                    trace_id = payload.get("trace_id")

        if not trace_id:
            raise RuntimeError("Finchvox did not resolve a trace ID for the session")

        if audio_path:
            path = Path(audio_path).expanduser()
            if path.exists() and path.is_file():
                form = aiohttp.FormData()
                with path.open("rb") as file_handle:
                    form.add_field(
                        "audio",
                        file_handle,
                        filename=path.name,
                        content_type="application/octet-stream",
                    )
                    async with session.post(
                        f"{base}/collector/livekit/{trace_id}/audio", data=form
                    ) as response:
                        response.raise_for_status()

    return trace_id


def session_report_json(report: Any) -> str:
    """Serialize a LiveKit SessionReport in a predictable, readable form."""
    return json.dumps(_report_to_dict(report), indent=2, ensure_ascii=False)
