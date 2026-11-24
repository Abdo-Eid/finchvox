"""Set aside LiveKit HTTP logs that have a job ID but no active span."""

import hashlib
import json
import time
from collections.abc import Callable
from pathlib import Path
from threading import Lock
from uuid import uuid4

from loguru import logger

from .config import LOG_BATCH_DIRECTORY, get_session_dir
from .livekit_reports import livekit_job_id, resolve_livekit_trace_id
from .log_writer import LogWriter

MAX_PENDING_JOBS = 32
MAX_JOB_LOG_BYTES = 4 * 1024 * 1024
MAX_PENDING_AGE = 24 * 60 * 60


class LiveKitJobLogs:
    def __init__(self, data_dir: Path, wake: Callable[[], None]):
        self.data_dir = data_dir
        self.pending = data_dir / "pending-livekit-logs"
        self._lock = Lock()
        self._wake = wake

    def save(self, record, resource, scope) -> bool:
        if scope.scope.name in {"chat_history", "evaluations"}:
            return False  # Structured LiveKit records aren't ordinary agent logs.
        log = LogWriter.convert_log(record, resource, scope)
        if not (job_id := livekit_job_id(log)):
            return False
        key = hashlib.sha256(job_id.encode()).hexdigest()
        line = (json.dumps(log) + "\n").encode()
        with self._lock:
            self.pending.mkdir(parents=True, exist_ok=True)
            path = self.pending / f"{key}.jsonl"
            if path.exists():
                size = path.stat().st_size
            else:
                size = 0
                if sum(1 for _ in self.pending.glob("*.jsonl")) >= MAX_PENDING_JOBS:
                    return False
            if size + len(line) > MAX_JOB_LOG_BYTES:
                return False
            with path.open("ab") as handle:
                handle.write(line)
        self._wake()
        return True

    def reconcile(self) -> None:
        for path in self.pending.glob("*.jsonl"):
            try:
                self._attach(path)
            except (OSError, ValueError):
                logger.exception(f"Could not attach pending LiveKit logs {path.name}")

    def _attach(self, path: Path) -> None:
        with self._lock, path.open("rb") as handle:
            job_id = livekit_job_id(json.loads(handle.readline()))
        trace_id = resolve_livekit_trace_id(
            self.data_dir, {"job_id": job_id}, exact_job=True
        )
        with self._lock:
            if trace_id:
                directory = get_session_dir(self.data_dir, trace_id) / LOG_BATCH_DIRECTORY
                directory.mkdir(exist_ok=True)
                path.replace(directory / f"{uuid4().hex}.jsonl")
            elif time.time() - path.stat().st_mtime >= MAX_PENDING_AGE:
                path.unlink()
                logger.warning(f"Expiring LiveKit logs without a matching trace: {job_id!r}")
