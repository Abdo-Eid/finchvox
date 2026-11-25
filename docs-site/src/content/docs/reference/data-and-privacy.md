---
title: Data and privacy
description: Know what is stored locally, what may still go to LiveKit Cloud, and how to manage saved calls.
---

## What's in a session

A session can contain audio, transcripts, tool inputs and results, traces, and Python logs. Treat the session directory and any downloaded zip as sensitive. By default the data directory is `~/.finchvox`; Compose uses a [named volume](../../examples/docker/#change-ports-or-back-up-sessions).

Finchvox has no login and binds to `127.0.0.1` by default. Keep it on your machine. If access from other machines is needed, add authentication and TLS (encrypted transport) before making it reachable.

## What goes to LiveKit Cloud

[Redirecting SDK uploads](../../start/connect/) changes where the SDK sends observability data, not where media or models run. The [Python integration](../../guides/python-integration/) sends a separate copy to Finchvox without disabling LiveKit's own uploads.

Do not assume `record=True` is local-only with LiveKit Cloud. Review your LiveKit recording settings before turning it on. If you use the Python integration, `allow_pii=False` strips conversational content from exported spans but does not redact separately exported logs, reports, or recordings.

## Move or remove a session

Download a saved session from its session page. To load that zip elsewhere, use **Import session** on the destination Finchvox's **Sessions** list. Check it for sensitive data before sharing.

Use **Delete session** on the session page to remove the local copy. End the call first so incoming data doesn't create it again. Deleting a session in Finchvox does not remove copies from LiveKit Cloud, `console-recordings/`, or any downloaded archive.
