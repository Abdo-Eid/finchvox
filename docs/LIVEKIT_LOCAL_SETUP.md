# LiveKit Agents + Finchvox: local observability setup

This guide connects a **LiveKit Agents (Python)** application to Finchvox so you can inspect sessions locally with a synchronized waveform, transcript, trace waterfall, logs, tool calls, handoffs, errors, and voice latency metrics.

Finchvox is the observability backend in this setup. Your agent exports OpenTelemetry directly to a Finchvox process you control.

> Finchvox is an independent open-source project/fork. It is not affiliated with or endorsed by LiveKit.

## What stays local

With the setup in this guide:

- custom OpenTelemetry traces are exported to your Finchvox collector (`localhost:4317` by default),
- stdlib logs can be exported to the same local collector,
- LiveKit `SessionReport` data can be uploaded to the local Finchvox HTTP server,
- finalized session audio can be attached to the local replay,
- Finchvox stores session files under `~/.finchvox` (or a directory you choose), and
- Finchvox anonymous product telemetry is disabled by default in this fork.

There is one important distinction: **LiveKit media transport and LiveKit Cloud observability are separate from Finchvox**. If your agent connects to LiveKit Cloud, the media still uses LiveKit Cloud. Whether LiveKit's own observability is uploaded depends on your LiveKit session/recording configuration. See [Local-only vs LiveKit Cloud](#local-only-vs-livekit-cloud) below.

## Prerequisites

- Python 3.12–3.14
- `uv` (recommended) or `pip`
- a working LiveKit Agents Python project
- a LiveKit server (LiveKit Cloud or self-hosted)

Finchvox needs LiveKit Agents 1.8.9 or newer. It reads the `lk.pii.*` and GenAI telemetry attributes those releases write, and does not read the attribute names used before 1.8. The span and attribute names were last checked against 1.8.11.

## 1. Install the fork

From this repository:

```bash
uv sync --extra livekit
```

Or with pip:

```bash
pip install -e ".[livekit]"
```

If Finchvox is checked out next to your agent project, you can install it into the agent environment directly:

```bash
cd /path/to/your-agent
uv pip install -e "/path/to/finchvox-livekit-agents[livekit]"
```

## 2. Start Finchvox locally

In a separate terminal:

```bash
uv run finchvox start
```

Open:

```text
http://localhost:3000
```

Default endpoints:

| Purpose | Endpoint |
| --- | --- |
| UI + HTTP API | `http://localhost:3000` |
| OTLP/gRPC traces + logs | `http://localhost:4317` |
| SessionReport auto-correlation | `POST http://localhost:3000/collector/livekit/report` |

Finchvox binds HTTP and OTLP/gRPC to `127.0.0.1` by default, so it is not exposed to your LAN unless you opt in.

To keep the data with your project instead of in your home directory:

```bash
uv run finchvox start --data-dir ./.finchvox-data
```

## 3. Add Finchvox tracing to your LiveKit agent

Initialize Finchvox **before the `AgentSession` starts**:

```python
import finchvox

tracer_provider = finchvox.init_livekit(
    service_name="my-livekit-agent",
    endpoint="http://localhost:4317",
    capture_logs=True,
    allow_pii=True,
    metadata={"environment": "local"},
)
```

`init_livekit()` creates an OpenTelemetry `TracerProvider`, sends spans to the local OTLP/gRPC collector, and registers it with LiveKit via `livekit.agents.telemetry.set_tracer_provider()`.

### About `allow_pii`

For a local Agent-Insights-style replay, `allow_pii=True` is normally what you want. It lets your custom exporter receive the content attributes LiveKit uses for transcripts, model responses, tool inputs/results, and related conversational details.

If you only want timing, model, token, and structural telemetry:

```python
tracer_provider = finchvox.init_livekit(
    service_name="my-livekit-agent",
    allow_pii=False,
)
```

With the supported LiveKit Agents 1.8.9+ baseline, this strips span content before it reaches the custom exporter. It does not redact separately exported logs, uploaded SessionReports, or recordings. The Trace and Metrics views still work, but the trace-derived transcript/tool-content experience is intentionally reduced.

## 4. Flush telemetry during shutdown

OpenTelemetry batches exports. Flush the provider before the job process exits:

```python
async def flush_observability():
    finchvox.flush_livekit(tracer_provider)

ctx.add_shutdown_callback(flush_observability)
```

This flushes both traces and Finchvox's OTLP log provider.

## 5. Attach the final LiveKit SessionReport

The LiveKit SDK can generate a `SessionReport` entirely inside your agent process. It contains final conversation history, events, usage/metrics, identifiers, and recording metadata.

Add an `on_session_end` callback:

```python
import logging

import finchvox
from finchvox.livekit import upload_session_artifacts
from livekit.agents import JobContext

logger = logging.getLogger("agent")


async def on_session_end(ctx: JobContext) -> None:
    report = ctx.make_session_report()

    # Make the just-finished spans visible to Finchvox before it tries to
    # correlate the report by LiveKit job/room identifiers.
    finchvox.flush_livekit(tracer_provider)

    try:
        trace_id = await upload_session_artifacts(report=report)
        logger.info("Finchvox replay finalized", extra={"finchvox_trace_id": trace_id})
    except Exception:
        # Observability should not make normal job shutdown fail.
        logger.exception("Failed to finalize Finchvox replay")
```

Register it on the server:

```python
@server.rtc_session(on_session_end=on_session_end)
async def entrypoint(ctx: JobContext):
    ...
```

Finchvox resolves the report to the OpenTelemetry trace using LiveKit job ID, room SID, or room name. You do not normally need to carry the trace ID yourself.

## 6. Complete example

```python
import logging

import finchvox
from finchvox.livekit import upload_session_artifacts
from livekit.agents import Agent, AgentServer, AgentSession, JobContext, inference

logger = logging.getLogger("my-agent")

tracer_provider = finchvox.init_livekit(
    service_name="my-livekit-agent",
    endpoint="http://localhost:4317",
    capture_logs=True,
    allow_pii=True,
)


class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a concise, helpful voice assistant.",
            stt=inference.STT(model="deepgram/nova-3"),
            llm=inference.LLM(model="google/gemma-4-31b-it"),
            tts=inference.TTS(model="inworld/inworld-tts-2"),
        )


server = AgentServer()


async def on_session_end(ctx: JobContext) -> None:
    report = ctx.make_session_report()
    finchvox.flush_livekit(tracer_provider)

    try:
        await upload_session_artifacts(report=report)
    except Exception:
        logger.exception("Failed to upload local Finchvox session artifacts")


@server.rtc_session(on_session_end=on_session_end)
async def entrypoint(ctx: JobContext):
    async def flush_observability():
        finchvox.flush_livekit(tracer_provider)

    ctx.add_shutdown_callback(flush_observability)

    # AgentSession uses LiveKit's bundled Silero VAD by default.
    session = AgentSession()
    await session.start(agent=Assistant(), room=ctx.room)


# Save as agent.py, then launch with:
# uv run python -m livekit.agents start agent.py
```

A runnable version lives in [`examples/livekit/agent.py`](../examples/livekit/agent.py).

## 7. Audio replay

OpenTelemetry spans do **not** contain replayable audio. Finchvox therefore treats audio as a separate session artifact.

### Fully self-hosted LiveKit

On current LiveKit Agents releases, session recording can create a local OGG file inside the job session directory. The resulting `SessionReport` exposes its path as `audio_recording_path`. If that path is present, `upload_session_artifacts(report=report)` uploads it to Finchvox automatically.

Make recording explicit when you want it:

```python
await session.start(
    agent=Assistant(),
    room=ctx.room,
    record={
        "audio": True,
        "transcript": True,
        "traces": False,
        "logs": False,
    },
)
```

For a self-hosted LiveKit server, LiveKit's Cloud observability endpoint is unavailable, while the SDK can still produce the local report/recording used by Finchvox.

### LiveKit Cloud while keeping custom telemetry in Finchvox

Your custom OpenTelemetry exporter still sends its copy of traces to Finchvox. However, LiveKit's `record` settings control LiveKit Cloud observability too. If your requirement is **no session audio/transcript upload to LiveKit Cloud**, use the LiveKit settings appropriate for that requirement (for example `record=False`) and attach audio to Finchvox from your own local recorder instead:

```python
await upload_session_artifacts(
    report=ctx.make_session_report(),
    audio_path="./recordings/session.ogg",
)
```

Do not assume `record=True` is local-only when your agent is connected to LiveKit Cloud.

Supported finalized Finchvox audio formats:

```text
.wav  .mp3  .ogg  .flac  .opus  .webm  .m4a
```

## 8. Running agent and Finchvox in Docker

`localhost` inside the agent container means the agent container itself, not your Finchvox container/host.

When Finchvox itself runs in a container, start it with `--host 0.0.0.0`; the default loopback bind intentionally accepts connections only from the same container/host. Do not publish the ports to an untrusted network without adding authentication/TLS or a trusted reverse proxy.

If both containers share a Docker network, use the Finchvox service name:

```bash
finchvox start --host 0.0.0.0
```

Then point the agent at the Finchvox service name:

```python
tracer_provider = finchvox.init_livekit(
    endpoint="http://finchvox:4317",
)
```

And send reports to the HTTP service name:

```python
await upload_session_artifacts(
    report=report,
    endpoint="http://finchvox:3000",
)
```

If Finchvox runs on the host and your agent runs in Docker Desktop, `host.docker.internal` is commonly available:

```text
http://host.docker.internal:4317
http://host.docker.internal:3000
```

On Linux, use an explicit host-gateway mapping or put both services on the same Docker network.

## 9. What Finchvox recognizes from LiveKit

The local trace adapter understands the spans LiveKit Agents 1.8 creates, including:

```text
agent_session
├── user_turn
│   ├── user_speaking
│   ├── eou_wait / eou_detection
│   └── keyterm_detection
├── agent_turn
│   ├── llm_request (llm_fallback_adapter when a fallback chain is used)
│   ├── function_tool
│   └── tts_request (tts_fallback_adapter / tts_stream_adapter)
├── update_agent          # handoff
├── event_loop_blocked    # the agent's event loop was blocked (red bar)
├── amd                   # answering machine detection
└── room_connect / wait_for_audio_track
```

Lifecycle spans such as `job_entrypoint`, `on_enter`, `session_close` and `rpc_call` are kept in the trace but hidden from the timeline unless they fail.

The **Metrics** tab also shows, when the agent provides them:

- blocked moments of the agent's event loop, with the task that blocked it,
- how long LiveKit took to dispatch the job to the agent,
- per-model usage (tokens, characters, audio seconds) from the uploaded `SessionReport`.

When emitted by the SDK, the UI also surfaces:

- end-to-end response latency,
- transcription delay,
- end-of-turn / endpointing delay,
- LLM time to first token/chunk,
- TTS time to first byte,
- speech/generation IDs,
- interruption state,
- tool arguments/results,
- model/provider names,
- token usage,
- exceptions and error spans,
- job/room/participant identifiers.

## 10. Logs

`capture_logs=True` adds an OpenTelemetry stdlib logging handler. Logs emitted while a LiveKit span is active retain trace/span correlation when the context is available and show up in Finchvox's **Logs** tab.

Use normal structured Python logging:

```python
logger = logging.getLogger("my-agent")
logger.info("calling booking service", extra={"booking_id": booking_id})
```

Disable local OTLP logs while keeping traces:

```python
finchvox.init_livekit(capture_logs=False)
```

## 11. Data directory and cleanup

Default data directory:

```text
~/.finchvox/
```

Project-local directory:

```bash
finchvox start --data-dir ./.finchvox-data
```

Finchvox stores each session under its trace ID. Treat this directory as potentially sensitive when `allow_pii=True`, because it can contain transcripts, tool payloads, logs, and recordings.

## 12. Troubleshooting

### Session never appears

Check that:

1. Finchvox is running and `localhost:4317` is reachable from the agent process.
2. `finchvox.init_livekit()` runs before `session.start()`.
3. the provider is flushed at shutdown.
4. Docker/container networking is not pointing `localhost` at the wrong container.

### Trace appears but transcript content is missing

Confirm `allow_pii=True`. Current LiveKit SDKs mark conversational content under `lk.pii.*` and GenAI content attributes; `allow_pii=False` intentionally strips those fields before your exporter sees them.

### Trace appears but no audio waveform/playback

Traces do not contain audio. Attach a finalized recording, or enable a LiveKit recording path appropriate for your deployment and then upload the `SessionReport`.

### SessionReport upload returns 404 / cannot resolve trace

Flush first:

```python
finchvox.flush_livekit(tracer_provider)
```

Then retry the report upload. Automatic correlation needs at least one completed span with matching LiveKit job/room identifiers. As a fallback, pass the known 32-character OTel trace ID explicitly.

### Logs are missing

Make sure `capture_logs=True` and your application uses Python `logging`. Some logs emitted outside an active span may not have trace correlation; they can still be exported, but a per-session UI cannot reliably assign an uncorrelated log to a session.

## References

- LiveKit export traces: https://docs.livekit.io/deploy/observability/tracing/
- LiveKit data hooks / SessionReport: https://docs.livekit.io/deploy/observability/data/
- LiveKit Agent Insights: https://docs.livekit.io/deploy/observability/insights/
- LiveKit Agents Python reference: https://docs.livekit.io/reference/python/livekit/agents/
