---
title: Connect with Python
description: Send a session to Finchvox without redirecting LiveKit Cloud uploads.
---

Use this path if you want the agent to send data to Finchvox while keeping its existing LiveKit Cloud uploads, or if you're recording a terminal call. Leave `LIVEKIT_OBSERVABILITY_URL` unset. Setting it alongside the Python integration can send the same spans to Finchvox twice.

## Install into the agent's environment

From your existing LiveKit Agents Python project:

```sh
uv add "finchvox @ git+https://github.com/Abdo-Eid/finchvox.git@main"
```

Use the Git URL. The Finchvox package on PyPI is the original project, not this fork. If you used the prebuilt Docker image for the server, the quickstart only publishes port `3000`. For these Python hooks, [publish port `4317` too](../../examples/docker/#connect-your-agent), or run Finchvox with the [source Compose setup](../../examples/docker/).

## Add the two hooks

Add `init_livekit()` before the session starts, and attach Finchvox's session-end callback to your existing handler:

```python
import finchvox
from finchvox.livekit import on_session_end
from livekit.agents import JobContext

finchvox.init_livekit(service_name="library-assistant")

@server.rtc_session(on_session_end=on_session_end)
async def entrypoint(ctx: JobContext):
    # Keep your existing session setup here.
    ...
```

The first hook sends traces and Python logs to the collector on port `4317`. The second sends the session report and any available finished recording to the HTTP collector on port `3000`. A trace does not contain any audio on its own.

## Keep an existing session-end callback

If your agent already has a callback, call `finalize_session()` inside it instead of replacing it:

```python
from finchvox.livekit import finalize_session

async def on_session_end(ctx: JobContext) -> None:
    # Keep your existing end-of-call code here.
    await finalize_session(ctx)
```

Use `await finalize_session(ctx, audio_path="./recordings/call.ogg")` to attach your own finalized recording. If Finchvox runs on custom ports, pass `endpoint=` (gRPC) and `http_endpoint=` (HTTP) to `init_livekit()`.

## Decide what to capture

Use `capture_logs=False` to turn off Finchvox's Python log export, or `allow_pii=False` to omit LiveKit conversation content from exported spans. That option does **not** redact logs, session reports, or recordings. See [Data and privacy](../../reference/data-and-privacy/) before using a real call.
