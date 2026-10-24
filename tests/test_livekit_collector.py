import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from finchvox.collector.audio_handler import AudioHandler
from finchvox.collector.collector_routes import register_collector_routes
from finchvox.collector.config import get_session_dir


@pytest.fixture
def livekit_collector(tmp_path: Path):
    app = FastAPI()
    audio_handler = AudioHandler(tmp_path)
    register_collector_routes(app, audio_handler)
    return TestClient(app), tmp_path


def test_livekit_report_is_saved_with_session(livekit_collector):
    client, data_dir = livekit_collector
    trace_id = "0123456789abcdef0123456789abcdef"
    report = {"room_name": "local-room", "events": [{"type": "handoff"}]}

    response = client.post(f"/collector/livekit/{trace_id}/report", json=report)

    assert response.status_code == 201
    report_file = get_session_dir(data_dir, trace_id) / "livekit_report.json"
    assert json.loads(report_file.read_text()) == report


def test_livekit_audio_accepts_supported_finalized_recording(livekit_collector):
    client, data_dir = livekit_collector
    trace_id = "abcdef0123456789abcdef0123456789"
    audio = b"webm" + (b"\x00" * 128)

    response = client.post(
        f"/collector/livekit/{trace_id}/audio",
        files={"audio": ("session.webm", audio, "audio/webm")},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["format"] == "webm"
    assert payload["size_bytes"] == len(audio)
    assert (get_session_dir(data_dir, trace_id) / "audio.webm").read_bytes() == audio


def test_livekit_collector_rejects_bad_trace_id(livekit_collector):
    client, _ = livekit_collector

    report_response = client.post("/collector/livekit/not-a-trace/report", json={})
    audio_response = client.post(
        "/collector/livekit/not-a-trace/audio",
        files={"audio": ("session.wav", b"audio", "audio/wav")},
    )

    assert report_response.status_code == 400
    assert audio_response.status_code == 400


def test_livekit_collector_rejects_unsupported_audio(livekit_collector):
    client, _ = livekit_collector
    trace_id = "0123456789abcdef0123456789abcdef"

    response = client.post(
        f"/collector/livekit/{trace_id}/audio",
        files={"audio": ("session.exe", b"nope", "application/octet-stream")},
    )

    assert response.status_code == 415


def test_livekit_audio_enforces_final_recording_limit_and_cleans_partial_file(
    livekit_collector, monkeypatch
):
    from finchvox.collector import collector_routes

    client, data_dir = livekit_collector
    trace_id = "fedcba9876543210fedcba9876543210"
    monkeypatch.setattr(collector_routes, "MAX_FINAL_AUDIO_FILE_SIZE", 4)

    response = client.post(
        f"/collector/livekit/{trace_id}/audio",
        files={"audio": ("session.webm", b"12345", "audio/webm")},
    )

    assert response.status_code == 413
    assert not (get_session_dir(data_dir, trace_id) / "audio.webm").exists()


def _write_trace_with_livekit_identity(data_dir: Path, trace_id: str, **identity):
    session_dir = get_session_dir(data_dir, trace_id)
    session_dir.mkdir(parents=True, exist_ok=True)
    attrs = []
    for key, value in identity.items():
        attrs.append({"key": key, "value": {"string_value": value}})
    span = {
        "trace_id_hex": trace_id,
        "span_id_hex": "0123456789abcdef",
        "name": "agent_turn",
        "start_time_unix_nano": "1",
        "end_time_unix_nano": "2",
        "attributes": attrs,
    }
    (session_dir / f"trace_{trace_id}.jsonl").write_text(json.dumps(span) + "\n")


def test_livekit_report_can_resolve_trace_from_job_id(livekit_collector):
    client, data_dir = livekit_collector
    trace_id = "11111111111111111111111111111111"
    _write_trace_with_livekit_identity(
        data_dir,
        trace_id,
        **{"lk.job_id": "AJ_local_123", "lk.room_sid": "RM_local_123"},
    )
    report = {
        "job_id": "AJ_local_123",
        "room_id": "RM_local_123",
        "room": "local-room",
        "events": [],
    }

    response = client.post("/collector/livekit/report", json=report)

    assert response.status_code == 201
    assert response.json()["trace_id"] == trace_id
    report_file = get_session_dir(data_dir, trace_id) / "livekit_report.json"
    assert json.loads(report_file.read_text()) == report


def test_livekit_report_can_resolve_trace_from_current_bare_context_ids(livekit_collector):
    client, data_dir = livekit_collector
    trace_id = "33333333333333333333333333333333"
    _write_trace_with_livekit_identity(
        data_dir,
        trace_id,
        **{"job_id": "AJ_current_123", "room_id": "RM_current_123"},
    )

    response = client.post(
        "/collector/livekit/report",
        json={
            "job_id": "AJ_current_123",
            "room_id": "RM_current_123",
            "room": "current-room",
            "events": [],
        },
    )

    assert response.status_code == 201
    assert response.json()["trace_id"] == trace_id


def test_livekit_report_auto_resolve_falls_back_to_room_name(livekit_collector):
    client, data_dir = livekit_collector
    trace_id = "22222222222222222222222222222222"
    _write_trace_with_livekit_identity(
        data_dir,
        trace_id,
        **{"lk.pii.room_name": "room-by-name"},
    )

    response = client.post(
        "/collector/livekit/report",
        json={"room": "room-by-name", "events": []},
    )

    assert response.status_code == 201
    assert response.json()["trace_id"] == trace_id


def test_livekit_report_auto_resolve_returns_actionable_404(livekit_collector):
    client, _ = livekit_collector

    response = client.post(
        "/collector/livekit/report",
        json={"job_id": "AJ_missing", "room_id": "RM_missing"},
    )

    assert response.status_code == 404
    assert "Flush traces first" in response.json()["detail"]
