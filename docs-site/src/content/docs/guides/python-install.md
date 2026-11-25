---
title: Install without Docker
description: Install the Finchvox fork from Git with uv instead of pulling the container.
---

If you don't use Docker, install the server with [uv](https://docs.astral.sh/uv/getting-started/installation/) and Git. Finchvox supports Python 3.12–3.14.

## Install the fork from Git

```sh
uv tool install --python 3.13 "finchvox @ git+https://github.com/Abdo-Eid/finchvox.git@main"
```

Plain `uv tool install finchvox` or `pip install finchvox` installs the original project from PyPI. This fork's changes aren't published there, so keep the Git URL. If the command isn't on your path, run `uv tool update-shell` and reopen your terminal.

## Start the server

```sh
finchvox start
```

Leave it running and open [localhost:3000](http://localhost:3000). Then [connect your LiveKit agent](../../start/connect/). If you redirect SDK uploads, you still don't need to install Finchvox inside the agent. Only the [Python hooks](../python-integration/) require that extra installation.
