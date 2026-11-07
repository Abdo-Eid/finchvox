# LiveKit Agent example with local Finchvox observability

This example shows the minimal integration for exporting **LiveKit Agents** telemetry to a Finchvox server running on your machine.

For the complete explanation—including privacy, LiveKit Cloud vs self-hosted behavior, audio recording, Docker networking, and troubleshooting—see [`../../docs/LIVEKIT_LOCAL_SETUP.md`](../../docs/LIVEKIT_LOCAL_SETUP.md).

## 1. Create the example environment

Use Python 3.12–3.14 and LiveKit Agents 1.8.9+.

From the repository root:

```bash
cd examples/livekit
uv sync
```

The example's `pyproject.toml` installs the repository root as an editable `finchvox[livekit]` dependency, so edits to Finchvox are picked up immediately.

## 2. Configure LiveKit and providers

Copy the template:

```bash
cp .env.example .env
```

Fill in your LiveKit credentials and the provider API keys required by the STT/LLM/TTS models you choose. Do not commit the resulting `.env` file.

## 3. Start Finchvox

In terminal 1, from `examples/livekit`:

```bash
uv run finchvox start --data-dir ../../.finchvox-data
```

Open `http://localhost:3000`.

The collector listens for OTLP/gRPC traces and logs on `localhost:4317`.

## 4. Start the agent

In terminal 2, also from `examples/livekit`:

```bash
uv run python -m livekit.agents download-files
uv run python -m livekit.agents start agent.py --dev
```

Join the room with your normal LiveKit client/playground and talk to the agent.

## What the example does

`agent.py`:

1. calls `finchvox.init_livekit()` before the session starts,
2. exports OpenTelemetry traces to `localhost:4317`,
3. exports Python logs to the same local collector,
4. flushes batched telemetry during shutdown, and
5. uploads the final `SessionReport` (plus a local recording when the report exposes one) to Finchvox.

The session then appears in the Finchvox UI with synchronized **Transcript**, **Trace**, **Logs**, and **Metrics** views.

## PII/content

The example uses `allow_pii=True` so a local replay can display transcript, model, and tool content. Set it to `False` to strip content from exported spans. This does not redact separately exported logs, uploaded SessionReports, or audio.

Treat `../../.finchvox-data` as sensitive when PII is enabled because it may contain transcript text, tool payloads, logs, and audio.

## Audio and LiveKit recording

OTel does not contain replayable room audio. `upload_session_artifacts()` automatically attaches `report.audio_recording_path` when LiveKit produced a finalized local recording.

LiveKit's own `record=` option is independent from the custom Finchvox exporter. If the agent is connected to LiveKit Cloud, do not assume `record=True` is local-only. See the full setup guide before choosing recording settings for a privacy-sensitive deployment.

## Docker/container note

Build from the repository root so the image installs this fork, not the public PyPI package:

```bash
docker build -f examples/livekit/Dockerfile -t finchvox-livekit-agent .
```

The image installs the root lockfile's LiveKit extra with `uv` and starts the agent using the current module-based CLI. Pass credentials at runtime rather than copying `.env` into the image. Image builds and model downloads require network access.

If the agent runs in a container and Finchvox runs elsewhere, `localhost:4317` points at the agent container and is usually wrong. Point `endpoint` at the Finchvox container/service name and pass the corresponding HTTP endpoint to `upload_session_artifacts()`.
