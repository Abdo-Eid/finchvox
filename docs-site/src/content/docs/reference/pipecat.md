---
title: Pipecat compatibility
description: Use the optional Pipecat integration and understand which platform this fork develops.
---

This fork develops the LiveKit integration first. Pipecat compatibility is maintained, but does not receive new Pipecat-only features. The supported baseline is Pipecat 1.14 or newer.

## Install and connect

From the Finchvox checkout, install the optional Pipecat dependencies:

```sh
uv sync --extra pipecat
```

Initialize Finchvox in your Pipecat bot and add `FinchvoxProcessor()` to its pipeline (the chain of steps that handle the call):

```python
import finchvox
from finchvox import FinchvoxProcessor

finchvox.init(service_name="my-pipecat-bot")
processor = FinchvoxProcessor()
```

See the [Pipecat example projects](https://github.com/Abdo-Eid/finchvox/tree/main/examples/pipecat) for pipeline placement. Don't use the LiveKit-specific hooks or environment variable with Pipecat.

If you want chunked Pipecat audio compressed to Opus in Docker, set `FINCHVOX_INSTALL_FFMPEG=true` and rebuild. For details, see the [repository Docker guide](https://github.com/Abdo-Eid/finchvox/blob/main/docs/DOCKER.md#settings).
