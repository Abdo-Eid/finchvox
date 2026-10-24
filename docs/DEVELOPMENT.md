# Development guide

This fork keeps Finchvox's Pipecat support while making the LiveKit Agents path a first-class local session debugger.

## Environment

Python 3.10+ is required. `uv` is recommended.

Install the LiveKit development path:

```bash
uv sync --extra livekit --extra dev
```

Install Pipecat support too when working on the original processor integration:

```bash
uv sync --extra livekit --extra pipecat --extra dev
```

Install pre-commit hooks:

```bash
uv run pre-commit install
```

Run formatting/lint fixes:

```bash
uv run scripts/fix-ruff.sh
```

## Run the local server

```bash
uv run finchvox start --data-dir ./.finchvox-data
```

The default bind address is `127.0.0.1`. For a Docker/network integration test, opt in with `--host 0.0.0.0`.

UI:

```text
http://localhost:3000
```

OTLP/gRPC:

```text
localhost:4317
```

## Tests

Run the full suite when all optional runtimes are installed:

```bash
uv run pytest -q
```

Run the core/LiveKit/UI suite without Pipecat processor tests:

```bash
files=$(find tests -maxdepth 1 -name 'test_*.py' \
  ! -name 'test_processor.py' -print | sort | tr '\n' ' ')
PYTHONPATH=src pytest -q $files
```

Useful targeted tests:

```bash
PYTHONPATH=src pytest -q \
  tests/test_adapters.py \
  tests/test_conversation_livekit.py \
  tests/test_livekit_collector.py \
  tests/test_livekit_helpers.py \
  tests/test_livekit_report.py \
  tests/test_metrics.py \
  tests/test_ui_routes.py
```

JavaScript syntax checks:

```bash
node --check ui/js/session_detail.js
node --check ui/js/logs_view.js
node --check ui/js/sessions_list.js
node --check ui/js/conversation.js
```

Python compile check:

```bash
PYTHONPATH=src python -m compileall -q src tests examples/livekit
```

## Manual OTLP smoke test

With Finchvox running, `otel-cli` can send a trace without either voice framework:

```bash
otel-cli span \
  --endpoint localhost:4317 \
  --name agent_session \
  --service livekit-smoke-test
```

For a realistic LiveKit session, use [`examples/livekit/agent.py`](../examples/livekit/agent.py) and follow [`LIVEKIT_LOCAL_SETUP.md`](LIVEKIT_LOCAL_SETUP.md).

## UI work

The session inspector is intentionally framework-aware rather than a generic OpenTelemetry viewer. The main files are:

```text
ui/session_detail.html
ui/css/app.css
ui/css/local-utilities.css
ui/js/session_detail.js
ui/js/conversation.js
ui/js/logs_view.js
```

The important interaction invariant is **one shared session clock**. Audio, transcript rows, trace bars, log rows, error markers, tools, and handoffs should all seek/highlight against the same session-relative time.

When changing LiveKit span normalization, add or update tests in `tests/test_adapters.py` and the `test_livekit_*` files. Keep fallbacks for older stored sessions when practical.

## Test fixtures and screenshots

UI smoke screenshots currently live under `docs/`:

```text
livekit-insights-sessions.png
livekit-insights-transcript.png
livekit-insights-trace.png
```

`VALIDATION.md` records the most recent validation performed for the packaged fork.
