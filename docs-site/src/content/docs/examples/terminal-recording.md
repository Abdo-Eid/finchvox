---
title: Record a terminal voice call
description: Capture a local microphone call with the LiveKit CLI without joining a LiveKit room.
---

Use the terminal console when you want a microphone test and replay without joining a LiveKit room. You still need the [LiveKit CLI](https://docs.livekit.io/intro/basics/cli/), Finchvox running locally, and a working Python agent. Model providers such as LiveKit Inference can still need network access and credentials.

## Connect the agent

Follow the [Python integration](../../guides/python-integration/) to configure `init_livekit()` and the session-end hook. Leave `LIVEKIT_OBSERVABILITY_URL` unset.

## Record and end the call

In the agent's project, run:

```sh
lk agent console --record agent.py
```

Speak to the agent, then exit the console cleanly so it can finish saving. Use Ctrl+C on Windows. After the call, look in `console-recordings/` for the CLI's local recording and report. Open **Sessions** in Finchvox and check the transcript, trace, and audio playback.

`--record` creates the console audio. Without it, don't expect a waveform. A browser console is not needed for this example.

## If you already redirect SDK uploads

As an alternative to installing Finchvox in the agent, keep [the upload URL](../../start/connect/) and add `record=True` to the agent's `session.start()` call. Use `--record` in the terminal as above. The CLI flag writes the audio; `record=True` tells the SDK to upload the session artifacts. Do not add the Python hooks as well.

This alternative was tested with synthetic console audio on LiveKit Agents 1.8.11 and 1.8.13. If it stops working after an upgrade, use the Python integration or check [Troubleshooting](../../guides/troubleshooting/).
