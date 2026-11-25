---
title: Connect a LiveKit agent
description: Redirect a room-based LiveKit agent’s observability uploads to your local Finchvox instance.
---

With Finchvox running, you can connect a room-based LiveKit agent by setting an environment variable. You don't need to install Finchvox in the agent's Python environment for this route.

## Set the upload URL

Set or replace this value in the agent's `.env`, or the environment used to start it. The process running the agent must be able to reach this address.

```dotenv
LIVEKIT_OBSERVABILITY_URL=http://localhost:3000
```

:::caution[This replaces the LiveKit Cloud upload]
While the variable is set, LiveKit Cloud's dashboard does not receive a second copy. The call's media and model requests still go where you configured them. To keep a Cloud copy, use the [Python integration](../../guides/python-integration/) instead. Don't use both integrations at once: spans can arrive twice.
:::

## Enable recording and traces

On LiveKit Cloud, ensure session recording and traces are on in the project, or enable them in your agent. On self-hosted LiveKit, turn recording on in the `session.start()` call instead of relying on a Cloud project setting:

```python
await session.start(agent=Assistant(), room=ctx.room, record=True)
```

Even if you're only checking the transcript, keep traces enabled: Finchvox uses them to attach the session report and audio to the right call.

## Make and end a call

Restart the agent so it picks up the variable. Join a room using your usual client, exchange a short test turn, then end the call so the SDK can send the recording. Open **Sessions** in Finchvox and look for the new call.

If the agent runs in a container, `localhost` points to that container, not the host or another container. See [Docker networking](../../examples/docker/#connect-your-agent) if Finchvox isn't reachable.

:::note[SDK compatibility]
LiveKit doesn't document `LIVEKIT_OBSERVABILITY_URL`. Finchvox tests the installed SDK's uploaders, but the setting could change in a future release. Use the [Python integration](../../guides/python-integration/) if you prefer documented SDK hooks.
:::
