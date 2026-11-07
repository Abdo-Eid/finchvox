# Development guide

This fork keeps Finchvox's Pipecat support while making the LiveKit Agents path a first-class local session debugger.

## Environment

Python 3.12–3.14 is supported. Use `uv` to manage the environment.

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
node --check ui/js/metrics_view.js
```

Browser-library regression tests (Node.js; no npm install required):

```bash
node --test scripts/test_core_browser_dependencies.cjs
uv run pytest -q tests/test_browser_vendoring.py
```

The Node tests load the real vendored Alpine reactivity engine, verify asset hashes,
and test player/chart integration through public-contract stubs. Rendering, audio
decoding, and browser interaction still need the manual smoke checks below.

Python compile check:

```bash
PYTHONPATH=src python -m compileall -q src tests examples/livekit
```

Docker smoke test, which builds and runs the real container (takes a minute or so; see [`DOCKER.md`](DOCKER.md)):

```bash
FINCHVOX_DOCKER_TESTS=1 uv run --extra dev pytest tests/test_docker.py
```

Lock file check, which confirms `uv.lock` still matches `pyproject.toml`:

```bash
uv lock --check
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

The automated tests and smoke checks above use local fixtures and synthetic sessions. They do not exercise a real LiveKit room or the speech, LLM and TTS providers, which need credentials and network access. Before a release, run the example against your own LiveKit deployment as an end-to-end check.

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

### Vendored browser libraries

The UI uses **Alpine.js 3.17.5**, **WaveSurfer.js 8.0.3**, and **Chart.js 4.6.1**.
Assets are served locally from `ui/lib`; there is no frontend build step, runtime
CDN requirement, or htmx dependency.

Exact sources, archive integrity, distribution payload hashes, and license sources
are pinned in `ui/lib/vendor-manifest.json`. Reproduce or verify them with:

```bash
uv run python scripts/vendor_browser_dependencies.py
uv run python scripts/vendor_browser_dependencies.py --check
```

These maintenance commands require network access. `--check` never writes files.
The updater verifies all sources before writing assets and `THIRD_PARTY_LICENSES.txt`,
and preserves upstream payloads byte-for-byte after a provenance banner. To update a
version, review its official release/migration notes, independently verify the new
archive integrity and payload hashes, and update the manifest and any embedded
dependency license sources before regenerating. Embedded dependency versions must
come from the released bundle, not just dependency ranges in npm metadata.

Keep native player/chart objects outside Alpine's proxies. Use the shallow-frozen
holders and `getAudioPlayer()` method; a JavaScript getter returning the player is
re-proxied by Alpine. Destroyed WaveSurfer 8 instances must never be reused. Catch
load/playback rejections and release events/charts during teardown.

### Browser smoke checklist

Use disposable/synthetic sessions rather than modifying real recordings. After a
library upgrade, load fresh assets (disable the browser cache or hard-refresh), then:

- Open the sessions list and toggle the import panel; check initialization happens once.
- Decode a stereo recording; check both channels, play/pause, waveform/keyboard seeks,
  seeking to zero, and transcript/trace/log clock alignment.
- Switch inspector tabs; render STT, LLM, TTS and turn-latency charts, hover points,
  select their spans, and verify audio seeking.
- Destroy/recreate the player and charts; reload audio twice rapidly to exercise
  cancellation. Check no duplicate hover/keyboard listeners or reused destroyed objects.
- Exercise retained-page (`pagehide.persisted`) pause and final teardown separately.
- Open a session without audio: the fallback should appear and the rest of the
  inspector remain usable. Its handled audio 404 is expected, not an uncaught failure.
- Inspect browser errors/console and server logs. Passing stub tests alone does not
  validate actual audio or canvas rendering; test other target browsers separately.

## Test fixtures and screenshots

UI smoke screenshots currently live under `docs/`:

```text
livekit-insights-sessions.png
livekit-insights-transcript.png
livekit-insights-trace.png
```
