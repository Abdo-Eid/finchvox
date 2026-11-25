---
title: Run Finchvox with Docker
description: Pull the Finchvox image and start the local dashboard. No source checkout or Python install required.
---

Start Docker or Docker Desktop. These commands download the Finchvox image and run it on your machine. You don't need to clone the repository or install a Python package.

## Pull and run

```sh
docker pull ghcr.io/abdo-eid/finchvox:main
docker run -d --name finchvox -p 127.0.0.1:3000:3000 -v finchvox-data:/data ghcr.io/abdo-eid/finchvox:main
```

Open [localhost:3000](http://localhost:3000). The **Sessions** list is empty until your agent sends data. The port is bound to this machine only because Finchvox has no login. The `finchvox-data` volume keeps sessions when the container is stopped or replaced.

## Before connecting the agent

If you already have a room-based LiveKit agent (Agents 1.8.9+), continue to [Connect a LiveKit agent](../connect/). If a different app answers on port `3000`, check [Troubleshooting](../../guides/troubleshooting/).

Can't pull the image or prefer another setup? See [Build from source with Compose](../../examples/docker/) or [Install without Docker](../../guides/python-install/).
