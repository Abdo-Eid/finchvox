# Changelog

All notable changes to **Finchvox** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased — LiveKit local insights fork

### Added

- Local-first LiveKit Agents OpenTelemetry integration with optional correlated OTLP logs.
- LiveKit `SessionReport` ingestion, report-to-trace correlation, and finalized recording upload.
- LiveKit-style synchronized session replay UI with Transcript, Trace, Logs, Metrics, Environment, error markers, and inspectors.
- Support for current `lk.pii.*` telemetry attributes plus legacy LiveKit attribute fallbacks.
- LiveKit voice latency normalization for E2E, transcription/end-of-turn delays, LLM TTFT, TTS TTFB, and queue wait where available.
- `docs/LIVEKIT_LOCAL_SETUP.md` and a runnable `examples/livekit/agent.py`.
- `--max-upload-mb` to configure the session upload limit (default 1024 MB). Unzipped size limits scale with it.
- LiveKit spans from Agents 1.8: `eou_detection`, `event_loop_blocked`, the LLM/TTS fallback and stream adapters, `amd`, and `wait_for_audio_track`. Lifecycle spans (`job_entrypoint`, `on_enter`, `session_close`, `rpc_call` and others) are hidden from the timeline unless they fail.
- The Metrics tab shows blocked moments of the agent's event loop, job dispatch latency, and per-model usage from the `SessionReport`.
- The Environment tab now works for LiveKit agents started with `init_livekit()`.

### Changed

- Finchvox anonymous product telemetry is disabled by default in this fork.
- UI assets are local; session pages no longer require the Tailwind Play CDN.
- Pipecat runtime packages moved to the optional `pipecat` extra so LiveKit-only installs stay smaller.
- The `livekit` extra installs only `livekit-agents`. The Silero, OpenAI, Deepgram and Cartesia plugin packages were not used; Agents ships its own VAD and LiveKit Inference.
- The LiveKit example uses `google/gemma-4-31b-it` instead of the deprecated `openai/gpt-4o-mini`, and no longer loads Silero by hand.
- The LiveKit adapter no longer reads attribute names used before Agents 1.8, and no longer lists span names the SDK does not create (`stt_node`, `stt_request`, `execute_tool`, `room_io`).

### Fixed

- Session zip uploads can no longer delete the data folder or other sessions through unsafe paths, and must keep every file inside the session's own folder.
- A failed session upload no longer loses the existing copy of that session.
- Session uploads are limited in size and are no longer read fully into memory.
- Span writes no longer re-read the whole trace file, so they stay fast as a session grows.
- Session uploads are refused if the trace would not load, and the existing copy is kept.
- A damaged session now returns an explanation instead of a bare server error, with details in the server log.
- Oversized audio uploads are refused as they arrive instead of being stored first.
- SessionReport and environment uploads are limited to 64 MB instead of being read into memory without a limit.
- Playing audio with a corrupt chunk no longer leaves a temp file behind, and returns an explanation.
- Playback no longer serves a truncated recording while ffmpeg is still compressing it, and a crash during compression no longer leaves a partial `audio.opus` treated as final.
- Session downloads are built in a temp file instead of in memory, store already-compressed audio without compressing it again, and leave out uploads or compressions still in progress.
- Uploading a recording replaces the previous one only once the new copy is complete, keeps one recording per session, and returns `409` instead of failing if the current recording is being played. Playback, session size and audio status now agree on which recording is used.
- `upload_session_artifacts` retries a recording upload for about 31 seconds when Finchvox answers `409` because the current recording is in use.
- Error logs now include tracebacks, and logging an error containing `{` no longer raises `KeyError`.

## [0.0.13] - 2026-2-12

- Add audio compression with automatic scheduling. WAV chunks are converted to Opus format using ffmpeg, with automatic background compression for inactive sessions.

## [0.0.12] - 2026-2-4

- Fix Error processing frame: 'AudioBufferProcessor' object has no attribute '\_last_user_frame_at' from pipecat-ai v0.0.101.

## [0.0.11] - 2026-2-3

- Add session environment information (OS, Python version, Python packages).

## [0.0.10] - 2026-2-2

- Add session download and upload for sharing sessions between machines.

## [0.0.9] - 2026-1-30

- Add error visibility improvements: error icons on spans with exceptions and ability to jump from log entries to their associated span.
- Add tool call visibility: tool icons on LLM spans and tool call names shown in the detail panel.
- Improve trace view readability with larger bars and fonts, better spacing between spans, and improved label overlap detection.

## [0.0.8] - 2026-1-27

- Add anonymous telemetry collection (can be disabled)

## [0.0.7] - 2026-1-25

- Add metrics view to session detail with a breakdown of TTFB by service (LLM, SST, TTS).

## [0.0.6] - 2026-1-20

- Show conversation STT / TTS messages prior to turn completion.
- By default, include modules from the project directory in log capture.
- Cap Pipecat's audio recorder silence insertion to 60 seconds max to prevent large audio file generation.

## [0.0.5] - 2026-1-19

- Add conversation section to session detail view to see a transcript of user <-> agent interactions.
- Add logs to raw data view.

## [0.0.4] - 2026-1-18

- Renames traces to sessions and make logs the default view

## [0.0.3] - 2-26-1-16

- Add log collection support for the standard logger and Loguru.
- Convert the trace view to a swimlane-style vs waterfall to make it easier to see how each service performs throughout the session.

## [0.0.2] - 2026-1-7

- Streamlined installation process with `finchvox.init()` and `FinchvoxProcessor`.

## [0.0.1] - 2026-1-4

Initial public release.
