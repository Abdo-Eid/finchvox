---
title: Troubleshooting
description: Diagnose missing sessions, audio, transcripts, and duplicate spans.
---

## No session appears

1. Open [the collector health endpoint](http://localhost:3000/collector/health) from the machine running Finchvox. Look for `finchvox-collector` in the response.
2. Check the address from the **agent's** environment too. [Docker networking](../../examples/docker/#connect-your-agent) changes what `localhost` means.
3. For [redirected uploads](../../start/connect/), restart the agent after setting the environment variable. Check that recording and traces are enabled. For [Python hooks](../python-integration/), call `init_livekit()` before the session and confirm the session-end callback runs.

## The trace appears, but there's no playback

Audio is a separate file. End the call cleanly so recording can finish, then check recording settings. In the terminal, use `lk agent console --record`. If you're redirecting the SDK's terminal uploads, enable `record=True` as well.

For redirected room uploads, keep traces enabled. Finchvox matches a recording to a call trace by LiveKit job ID. If it receives the recording first, it queues it until a matching trace arrives; when the match is ambiguous, it won't guess.

## The transcript, logs, or timings are missing

- **Transcript or tool content:** with the Python exporter, `allow_pii=False` omits conversation content from spans. With redirected uploads, check the SDK's recording and redaction settings instead.
- **Logs:** check `capture_logs` if using Python hooks and emit through Python's `logging`. Logs without a usable trace or LiveKit job identifier may not be assignable to a call.
- **Timings:** Finchvox shows the data the SDK actually emits. A model that handles speech in real time can expose different timing fields than separate speech, language, and voice models.

## Every span appears twice

Check whether both `LIVEKIT_OBSERVABILITY_URL` and `init_livekit()` are active. Pick one [integration](../../start/connect/#set-the-upload-url), restart the agent, and make a fresh test call.

For deeper collector and SDK troubleshooting, see the [repository setup guide](https://github.com/Abdo-Eid/finchvox/blob/main/docs/LIVEKIT_LOCAL_SETUP.md).
