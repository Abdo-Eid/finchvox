"""The no-code hookup against the installed LiveKit SDK.

LiveKit does not document LIVEKIT_OBSERVABILITY_URL, so this test runs the SDK's
own uploaders (its OTLP exporters and session-recording upload) against a real
Finchvox server. If an SDK upgrade changes the paths or the format, this fails
instead of Finchvox silently receiving nothing.
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import pytest
import uvicorn

pytest.importorskip("livekit.agents")

from finchvox.server import UnifiedServer

UPLOADER = Path(__file__).with_name("livekit_cloud_uploader.py")
JOB_ID = "AJ_compat"
AUDIO = b"OggS" + bytes(range(256)) * 16


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


@pytest.fixture
def finchvox_url(tmp_path):
    port = _free_port()
    server = uvicorn.Server(
        uvicorn.Config(
            UnifiedServer(data_dir=tmp_path / "data").app,
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    assert server.started
    yield f"http://127.0.0.1:{port}", tmp_path / "data"
    server.should_exit = True
    thread.join(timeout=10)


def test_the_sdks_own_uploads_become_a_complete_session(finchvox_url, tmp_path):
    url, data_dir = finchvox_url
    audio_path = tmp_path / "audio.ogg"
    audio_path.write_bytes(AUDIO)

    result = subprocess.run(
        [sys.executable, str(UPLOADER), JOB_ID, str(audio_path)],
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
        env={
            **os.environ,
            "LIVEKIT_OBSERVABILITY_URL": url,
            # Ensure this call's first span batch waits for the final flush.
            "OTEL_BSP_SCHEDULE_DELAY": "60000",
            "LIVEKIT_API_KEY": "compat-key",
            "LIVEKIT_API_SECRET": "compat-secret-compat-secret-compat-secret",
        },
    )
    assert result.returncode == 0, result.stderr
    assert "uploaded" in result.stdout

    sessions = [p for p in (data_dir / "sessions").iterdir() if p.is_dir()]
    assert len(sessions) == 1
    session = sessions[0]
    trace_id = session.name

    span_names = {
        json.loads(line)["name"]
        for line in (session / f"trace_{trace_id}.jsonl").read_text().splitlines()
    }
    assert {"agent_session", "agent_turn"} <= span_names

    logs = (session / f"logs_{trace_id}.jsonl").read_text()
    assert "hello from the agent" in logs

    report_path = session / "livekit_report.json"
    deadline = time.monotonic() + 5
    while not report_path.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["job_id"] == JOB_ID
    contents = [item.get("content") for item in report["chat_history"]["items"]]
    assert ["hello"] in contents and ["hi there"] in contents
    with urllib.request.urlopen(f"{url}/api/sessions/{trace_id}/conversation", timeout=5) as response:
        conversation = json.load(response)
    assert "مرحبا" in json.dumps(conversation, ensure_ascii=False)

    assert (session / "audio.ogg").read_bytes() == AUDIO
    logs_url = f"{url}/api/sessions/{trace_id}/logs"
    deadline = time.monotonic() + 5
    while True:
        with urllib.request.urlopen(logs_url, timeout=5) as response:
            logs = json.load(response)
        if "outside an active span" in json.dumps(logs) or time.monotonic() >= deadline:
            break
        time.sleep(0.05)
    assert "outside an active span" in json.dumps(logs)
    assert "chat item" not in json.dumps(logs)
    assert "compat-secret" not in "".join(
        p.read_text(errors="ignore") for p in session.iterdir() if p.is_file()
    )


def test_large_recording_round_trips_over_http(finchvox_url):
    url, _ = finchvox_url
    trace_id = "a" * 32
    recording = b"OggS" * (8 * 1024 * 1024)
    boundary = "finchvox-test-recording"
    body = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="audio"; filename="test.ogg"\r\n'
        "Content-Type: audio/ogg\r\n\r\n"
    ).encode() + recording + f"\r\n--{boundary}--\r\n".encode()
    request = urllib.request.Request(
        f"{url}/collector/livekit/{trace_id}/audio",
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        assert response.status == 201
    with urllib.request.urlopen(
        f"{url}/api/sessions/{trace_id}/audio", timeout=15
    ) as response:
        assert response.read() == recording
