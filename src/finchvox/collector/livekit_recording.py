"""The session-end upload LiveKit Agents sends to ``LIVEKIT_OBSERVABILITY_URL``.

It is a multipart form with three parts: ``header``, a LiveKit protobuf message
(``MetricsRecordingHeader``) whose ``session_summary`` is the SessionReport as
JSON without its chat history; ``chat_history``, that history as JSON; and
``audio``, the call recording. Together they give Finchvox the same report and
recording that ``finchvox.livekit.on_session_end`` uploads.
"""

import asyncio
import hashlib
import json
import shutil
import tempfile
import time
from contextlib import asynccontextmanager, suppress
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from google.protobuf.message import DecodeError
from livekit.protocol.metrics import MetricsRecordingHeader
from loguru import logger
from starlette.concurrency import run_in_threadpool

from .audio_handler import AudioHandler, RecordingInUseError, RecordingTooLargeError
from .config import (
    ALLOWED_FINAL_AUDIO_FORMATS,
    MAX_FINAL_AUDIO_FILE_SIZE,
    MAX_JSON_BODY_BYTES,
    get_session_dir,
)
from .livekit_job_logs import LiveKitJobLogs
from .livekit_reports import resolve_livekit_trace_id

PENDING_CHECK_SECONDS = 30
PENDING_MAX_AGE_SECONDS = 24 * 60 * 60
PENDING_MAX_RECORDINGS = 8
PENDING_DIRECTORY = "pending-livekit-recordings"


class RecordingUploadError(ValueError):
    """The upload is not a LiveKit recording upload Finchvox can read."""


class UnsupportedRecordingFormat(ValueError):
    """The recording's file type is not one Finchvox plays."""


class PendingRecordingsFull(Exception):
    """The pending recording directory has reached its configured limit."""


def report_from_upload(header: bytes, chat_history: bytes | None) -> dict:
    """Rebuild the SessionReport from the header and the chat history parts."""
    try:
        message = MetricsRecordingHeader.FromString(header)
    except DecodeError as e:
        raise RecordingUploadError("header is not a LiveKit MetricsRecordingHeader") from e

    report: dict = {}
    if message.session_summary:
        try:
            summary = json.loads(message.session_summary)
        except ValueError as e:
            raise RecordingUploadError("session_summary is not valid JSON") from e
        if isinstance(summary, dict):
            report.update(summary)
    for key, value in (
        ("job_id", message.job_id),
        ("room_id", message.room_id),
        ("room", message.room_name),
    ):
        if value and not report.get(key):
            report[key] = value
    if message.job_id and report.get("job_id") != message.job_id:
        raise RecordingUploadError("header and session summary disagree on job ID")
    if not isinstance(report.get("job_id"), str) or not report["job_id"].strip():
        raise RecordingUploadError("recording carries no LiveKit job ID")

    if chat_history:
        try:
            history = json.loads(chat_history)
        except ValueError as e:
            raise RecordingUploadError("chat_history is not valid JSON") from e
        if isinstance(history, dict):
            report["chat_history"] = history
    return report


async def _read_limited(upload: UploadFile, limit: int, name: str) -> bytes:
    data = await upload.read(limit + 1)
    if len(data) > limit:
        raise RecordingUploadError(f"{name} is larger than {limit} bytes")
    return data


class LiveKitRecordingReceiver:
    """Save session-end uploads before LiveKit flushes its last spans."""

    def __init__(self, audio_handler: AudioHandler):
        self.audio_handler = audio_handler
        self.pending_dir = audio_handler.data_dir / PENDING_DIRECTORY
        self._enqueue_lock = asyncio.Lock()
        self._wake = asyncio.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self.job_logs = LiveKitJobLogs(audio_handler.data_dir, self.notify_trace_written)

    @asynccontextmanager
    async def lifespan(self, app):
        """Retry attachment for pending uploads, including after a restart."""
        await run_in_threadpool(self._discard_incomplete_uploads)
        stop = asyncio.Event()
        self._loop = asyncio.get_running_loop()
        worker = asyncio.create_task(self._reconcile_loop(stop))
        try:
            yield
        finally:
            self._loop = None
            stop.set()
            self._wake.set()
            await worker

    def notify_trace_written(self) -> None:
        """Wake attachment from either HTTP or gRPC's writer thread."""
        if (loop := self._loop) is not None:
            with suppress(RuntimeError):  # The server loop may already be closing.
                loop.call_soon_threadsafe(self._wake.set)

    async def receive(
        self,
        header: UploadFile,
        chat_history: UploadFile | None,
        audio: UploadFile | None,
    ) -> None:
        """Return once the upload is saved, not when its trace is available."""
        extension = ".ogg"
        if audio is not None:
            extension = Path(audio.filename or "recording.ogg").suffix.lower() or ".ogg"
            if extension not in ALLOWED_FINAL_AUDIO_FORMATS:
                raise UnsupportedRecordingFormat(f"Unsupported recording format: {extension}")

        header_bytes = await _read_limited(header, MAX_JSON_BODY_BYTES, "header")
        chat_bytes = (
            await _read_limited(chat_history, MAX_JSON_BODY_BYTES, "chat_history")
            if chat_history is not None
            else None
        )
        report = report_from_upload(header_bytes, chat_bytes)
        key = hashlib.sha256(report["job_id"].encode()).hexdigest()
        async with self._enqueue_lock:
            await run_in_threadpool(self.pending_dir.mkdir, parents=True, exist_ok=True)
            destination = self.pending_dir / key
            if destination.exists():
                return  # A retry must not replace a pending, acknowledged upload.
            if len(await run_in_threadpool(self._pending)) >= PENDING_MAX_RECORDINGS:
                raise PendingRecordingsFull("Too many LiveKit recordings are awaiting traces")

            staging = Path(
                await run_in_threadpool(
                    tempfile.mkdtemp, prefix=".upload-", dir=self.pending_dir
                )
            )
            try:
                await run_in_threadpool(
                    (staging / "livekit_report.json").write_text,
                    json.dumps(report, ensure_ascii=False, separators=(",", ":")),
                    encoding="utf-8",
                )
                if audio is not None:
                    await self._stage_audio(staging / f"audio{extension}", audio)
                await run_in_threadpool(staging.rename, destination)
            finally:
                await run_in_threadpool(shutil.rmtree, staging, ignore_errors=True)
        self._wake.set()

    @staticmethod
    async def _stage_audio(destination: Path, upload: UploadFile) -> None:
        total = 0
        async with aiofiles.open(destination, "wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > MAX_FINAL_AUDIO_FILE_SIZE:
                    raise RecordingTooLargeError("Finalized audio exceeds the upload limit")
                await output.write(chunk)

    def _pending(self) -> list[Path]:
        if not self.pending_dir.exists():
            return []
        return [
            path
            for path in self.pending_dir.iterdir()
            if path.is_dir() and not path.name.startswith(".")
        ]

    def _discard_incomplete_uploads(self) -> None:
        for path in self.pending_dir.glob(".upload-*"):
            try:
                shutil.rmtree(path)
            except OSError:
                logger.exception(f"Could not remove incomplete LiveKit upload {path.name}")

    async def _reconcile_loop(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self._wake.clear()
            try:
                await run_in_threadpool(self.job_logs.reconcile)
                for path in await run_in_threadpool(self._pending):
                    if stop.is_set():
                        return
                    try:
                        await self._attach(path)
                    except OSError:
                        logger.exception(f"Could not attach pending LiveKit recording {path.name}")
            except OSError:
                logger.exception("Could not list pending LiveKit recordings")
            try:
                await asyncio.wait_for(self._wake.wait(), timeout=PENDING_CHECK_SECONDS)
            except TimeoutError:
                pass

    async def _attach(self, path: Path) -> None:
        report_file = path / "livekit_report.json"
        # A missing report means attachment finished before the previous process
        # could remove the spool directory.
        if not report_file.exists():
            await run_in_threadpool(shutil.rmtree, path)
            return
        try:
            report = json.loads(await run_in_threadpool(report_file.read_text, encoding="utf-8"))
        except (UnicodeError, ValueError):
            logger.exception(f"Invalid pending LiveKit report in {path.name}")
            return
        if not isinstance(report, dict) or not isinstance(report.get("job_id"), str):
            logger.error(f"Invalid pending LiveKit report in {path.name}")
            return
        trace_id = await run_in_threadpool(
            resolve_livekit_trace_id, self.audio_handler.data_dir, report, exact_job=True
        )
        if not trace_id:
            if time.time() - path.stat().st_mtime >= PENDING_MAX_AGE_SECONDS:
                logger.warning(
                    f"Expiring LiveKit recording without a matching trace: {report['job_id']!r}"
                )
                await run_in_threadpool(shutil.rmtree, path)
            return
        session_dir = get_session_dir(self.audio_handler.data_dir, trace_id)
        audio = next(path.glob("audio.*"), None)
        if audio is not None:
            try:
                await run_in_threadpool(
                    self.audio_handler.install_final_recording, audio, session_dir / audio.name
                )
            except RecordingInUseError:
                return  # Windows cannot replace a playing recording.
        await run_in_threadpool(report_file.replace, session_dir / report_file.name)
        await run_in_threadpool(shutil.rmtree, path)
        logger.info(f"Attached LiveKit recording to trace {trace_id[:8]}...")
