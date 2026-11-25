---
title: Server and UI settings
description: Look up Finchvox's ports, storage, upload limits, and browser display settings.
---

## Server flags

Pass these to `finchvox start`, or run `finchvox start --help` for the installed version.

| Flag | Default | What it changes |
| --- | --- | --- |
| `--host` | `127.0.0.1` | Address both collectors and the UI listen on |
| `--port` | `3000` | HTTP port for the UI and uploads |
| `--grpc-port` | `4317` | Port for OpenTelemetry traces and logs from the Python integration |
| `--data-dir` | `~/.finchvox` | Where sessions are saved |
| `--max-upload-mb` | `1024` | Maximum session zip size for UI imports, in MB |
| `--telemetry` | `false` | Anonymous Finchvox product telemetry, separate from agent data |

For example, use a project-local data directory and move the UI and HTTP collector to port `3100`:

```sh
finchvox start --port 3100 --data-dir ./.finchvox-data
```

When changing a port, update the corresponding agent endpoint too. For Compose environment variables, see [the Docker example](../../examples/docker/#change-ports-or-back-up-sessions).

## Display preferences

Open the gear icon in the local app to change the theme, text size, time format, and initial session tab. Preferences are stored in your browser. Settings also shows the server's startup configuration read-only; change that configuration in the terminal.
