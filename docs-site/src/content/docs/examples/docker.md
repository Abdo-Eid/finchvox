---
title: Docker Compose and networking
description: Build Finchvox from source with Docker Compose, connect agents across containers, and keep your session data.
---

For most setups, [pull and run the published image](../../start/install/). Use Docker Compose to build Finchvox from a checkout, or use the networking notes below when the agent runs in a container.

## Start Finchvox

Clone the [Finchvox fork](https://github.com/Abdo-Eid/finchvox) and start Compose:

```sh
git clone https://github.com/Abdo-Eid/finchvox.git
cd finchvox
docker compose up -d --build
docker compose logs -f
```

Open [localhost:3000](http://localhost:3000). The container publishes the dashboard and HTTP collector on `3000` and the gRPC collector for Python integrations on `4317`. Both are reachable only from the machine running Docker by default.

## Connect your agent

| Where the agent runs | Upload URL for room calls | Python integration gRPC endpoint |
| --- | --- | --- |
| On the host running Compose | `http://localhost:3000` | `http://localhost:4317` |
| In a container on the same Compose network | `http://finchvox:3000` | `http://finchvox:4317` |

Set the upload URL using [`LIVEKIT_OBSERVABILITY_URL`](../../start/connect/) **or** pass the gRPC endpoint to [`init_livekit()`](../../guides/python-integration/). In the Python path, set `http_endpoint=` as well when the HTTP port is not `3000`. Don't use both integrations at once.

If you started the prebuilt image with `docker run` and use Python hooks from the host, recreate the container with `-p 127.0.0.1:4317:4317` in addition to its existing port and volume flags. Reuse the named volume to keep your sessions.

If the agent is in a different container, `localhost` refers to that container. Put both services on the same Docker network so the agent can use the Finchvox service name. In Docker Desktop, when Finchvox runs directly on the host, `host.docker.internal` can be used from the agent container if the host listener is reachable. Don't expose an unauthenticated collector to the network just to make this work.

## Change ports or back up sessions

If Docker can't bind a port, change `FINCHVOX_HTTP_PORT` or `FINCHVOX_GRPC_PORT` in the `.env` next to `compose.yaml`. Restart the service and update the agent's address to match. On Windows, check that [the health endpoint](http://localhost:3000/collector/health) actually answers from Finchvox; another process can already have `localhost:3000`.

```sh
docker compose cp finchvox:/data ./finchvox-backup
docker compose down
```

`docker compose down` keeps the named volume. Adding `-v` removes it and deletes the saved sessions. For more Compose settings and backup notes, see the [repository Docker guide](https://github.com/Abdo-Eid/finchvox/blob/main/docs/DOCKER.md).
