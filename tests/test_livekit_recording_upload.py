"""The recording upload LiveKit sends at session end when LIVEKIT_OBSERVABILITY_URL
points at Finchvox: a protobuf header holding the session report, the chat history,
and the audio."""

import json
import time

import pytest
from fastapi.testclient import TestClient
from livekit.protocol.metrics import MetricsRecordingHeader
from opentelemetry.proto.common.v1.common_pb2 import AnyValue, KeyValue
from opentelemetry.proto.trace.v1.trace_pb2 import ResourceSpans, ScopeSpans, Span

from finchvox.collector import livekit_recording
from finchvox.collector.config import get_session_dir
from finchvox.server import UnifiedServer

TRACE_ID = "0123456789abcdef0123456789abcdef"
JOB_ID = "AJ_recording"
AUDIO = b"OggS" + bytes(range(256)) * 8
CHAT = {
    "items": [
        {"id": "m1", "type": "message", "role": "user", "content": ["hello"], "created_at": 1.5},
        {"id": "m2", "type": "message", "role": "assistant", "content": ["hi"], "created_at": 2.0},
    ]
}


@pytest.fixture
def server(tmp_path, monkeypatch):
    monkeypatch.setattr(livekit_recording, "PENDING_CHECK_SECONDS", 0.05)
    unified = UnifiedServer(data_dir=tmp_path)
    with TestClient(unified.app) as client:
        yield unified, client, get_session_dir(tmp_path, TRACE_ID)


def wait_for(path):
    deadline = time.monotonic() + 3
    while not path.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert path.exists()
    return path


def write_span(unified, job_id=JOB_ID):
    span = Span(
        trace_id=bytes.fromhex(TRACE_ID),
        span_id=bytes.fromhex("2222222222222222"),
        name="agent_session",
        start_time_unix_nano=1_000_000_000,
        end_time_unix_nano=9_000_000_000,
        attributes=[
            KeyValue(key="job_id", value=AnyValue(string_value=job_id)),
            KeyValue(key="room_id", value=AnyValue(string_value="RM_1")),
        ],
    )
    unified.span_writer.write_span(span, ResourceSpans(), ScopeSpans())


def header(job_id=JOB_ID) -> bytes:
    summary = {"job_id": job_id, "room_id": "RM_1", "room": "test-room", "usage": []}
    return MetricsRecordingHeader(
        room_id="RM_1", job_id=job_id, duration=8000, session_summary=json.dumps(summary)
    ).SerializeToString()


def upload(client, *, chat=True, audio=True, header_bytes=None, headers=None):
    files = {"header": ("header.binpb", header_bytes or header(), "application/protobuf")}
    if chat:
        files["chat_history"] = ("chat_history.json", json.dumps(CHAT), "application/json")
    if audio:
        files["audio"] = ("recording.ogg", AUDIO, "audio/ogg")
    return client.post("/observability/recordings/v0", files=files, headers=headers or {})


def test_the_report_and_recording_are_attached_to_the_matching_trace(server):
    unified, client, session_dir = server
    write_span(unified)

    response = upload(client)

    assert response.status_code == 202
    report = json.loads(wait_for(session_dir / "livekit_report.json").read_text())
    assert report["job_id"] == JOB_ID
    assert report["room"] == "test-room"
    assert [item["id"] for item in report["chat_history"]["items"]] == ["m1", "m2"]
    assert (session_dir / "audio.ogg").read_bytes() == AUDIO


def test_without_transcript_or_audio_only_the_report_is_stored(server):
    unified, client, session_dir = server
    write_span(unified)

    response = upload(client, chat=False, audio=False)

    assert response.status_code == 202
    report = json.loads(wait_for(session_dir / "livekit_report.json").read_text())
    assert "chat_history" not in report
    assert not (session_dir / "audio.ogg").exists()


def test_a_recording_is_acknowledged_before_the_sdk_flushes_its_trace(server):
    unified, client, session_dir = server

    response = upload(client)

    assert response.status_code == 202
    assert not session_dir.exists()
    write_span(unified)
    wait_for(session_dir / "livekit_report.json")
    assert (session_dir / "audio.ogg").read_bytes() == AUDIO


def test_same_room_is_not_a_match_for_a_different_job(server):
    unified, client, session_dir = server
    write_span(unified, job_id="AJ_other")

    response = upload(client)

    assert response.status_code == 202
    time.sleep(0.15)
    assert not (session_dir / "livekit_report.json").exists()


def test_staged_recording_survives_restart(tmp_path, monkeypatch):
    monkeypatch.setattr(livekit_recording, "PENDING_CHECK_SECONDS", 0.05)
    with TestClient(UnifiedServer(data_dir=tmp_path).app) as client:
        assert upload(client).status_code == 202

    restarted = UnifiedServer(data_dir=tmp_path)
    write_span(restarted)
    with TestClient(restarted.app):
        wait_for(get_session_dir(tmp_path, TRACE_ID) / "livekit_report.json")


def test_duplicate_upload_does_not_consume_another_pending_slot(server, monkeypatch):
    monkeypatch.setattr(livekit_recording, "PENDING_MAX_RECORDINGS", 1)
    unified, client, session_dir = server
    assert upload(client).status_code == 202
    assert upload(client, audio=False).status_code == 202
    assert upload(client, header_bytes=header("AJ_second")).status_code == 507
    write_span(unified)
    wait_for(session_dir / "livekit_report.json")
    assert (session_dir / "audio.ogg").read_bytes() == AUDIO


def test_failed_upload_does_not_leave_a_pending_recording(server, monkeypatch):
    monkeypatch.setattr(livekit_recording, "MAX_FINAL_AUDIO_FILE_SIZE", len(AUDIO) - 1)
    unified, client, _ = server
    assert upload(client).status_code == 413
    pending = unified.data_dir / livekit_recording.PENDING_DIRECTORY
    assert list(pending.iterdir()) == []


def test_unmatched_upload_expires(server, monkeypatch):
    monkeypatch.setattr(livekit_recording, "PENDING_MAX_AGE_SECONDS", 0)
    unified, client, session_dir = server
    assert upload(client).status_code == 202
    pending = unified.data_dir / livekit_recording.PENDING_DIRECTORY
    deadline = time.monotonic() + 3
    while any(pending.iterdir()) and time.monotonic() < deadline:
        time.sleep(0.02)
    assert not any(pending.iterdir())
    assert not session_dir.exists()


def test_a_header_that_is_not_livekits_is_rejected(server):
    unified, client, _ = server
    write_span(unified)

    response = upload(client, header_bytes=b"\xff\xff\xff not protobuf")

    assert response.status_code == 400


def test_the_upload_token_is_never_stored(server):
    unified, client, session_dir = server
    write_span(unified)

    upload(client, headers={"Authorization": "Bearer abc.do-not-store-me.xyz"})
    wait_for(session_dir / "livekit_report.json")

    stored = "".join(
        p.read_text(errors="ignore") for p in session_dir.iterdir() if p.is_file()
    )
    assert "do-not-store-me" not in stored
