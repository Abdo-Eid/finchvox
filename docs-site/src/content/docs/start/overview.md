---
title: Overview
description: Learn what Finchvox captures and choose a path to your first replay.
---

Finchvox is a local session debugger for voice agents. Open one finished call and inspect its audio, transcript, traces, logs, and timings against the same clock. A **trace** is a timeline of the work the agent did, such as recognizing speech or calling a tool.

If an agent takes too long to reply, start at the pause in the transcript and inspect the work happening at that moment. Finchvox helps explain that call; it does not send alerts or monitor performance across calls.

## Get to your first replay

1. [Pull and run Finchvox with Docker](../install/).
2. [Point your LiveKit agent at Finchvox](../connect/) with `LIVEKIT_OBSERVABILITY_URL`.
3. End a call and [open the replay](../replay/).

Already running a LiveKit Agents Python project? Follow this path in order. If you don't have an agent yet, start with the [runnable LiveKit example](../../examples/livekit-agent/). If you just want a look, try the [synthetic replay](../replay/#try-a-synthetic-session).

## What stays local

Finchvox runs on your machine and stores the data it receives there. It does not sit in the call or listen to LiveKit server traffic. Your agent sends traces and logs as it works, then sends its session report and a finished recording when configured to do so.

Your LiveKit server and model providers still handle the call and inference as configured. See [Data and privacy](../../reference/data-and-privacy/) before recording real calls.

Finchvox is an independent open-source project, not affiliated with or endorsed by LiveKit.
