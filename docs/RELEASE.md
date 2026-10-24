# Releasing this Finchvox fork

This repository is based on the MIT-licensed Finchvox project. If you publish your own fork, use your own repository/package release process and keep the upstream license notice.

## Before releasing

1. Update `pyproject.toml` with the version you intend to publish.
2. Update `CHANGELOG.md`.
3. Run the validation commands in [`DEVELOPMENT.md`](DEVELOPMENT.md).
4. Confirm the LiveKit setup guide still matches the current example:

```bash
PYTHONPATH=src python -m compileall -q src tests examples/livekit
node --check ui/js/session_detail.js
node --check ui/js/logs_view.js
node --check ui/js/sessions_list.js
uv lock --check
```

5. Run the test suite with the optional integrations you intend to support:

```bash
uv sync --extra livekit --extra pipecat --extra dev
uv run pytest -q
```

## Build

```bash
rm -rf dist/
uv build
```

Inspect the wheel/sdist before publishing:

```bash
ls -lh dist/
python -m zipfile -l dist/*.whl | head -100
```

The wheel should include the Finchvox Python package and the bundled local UI assets.

## Publishing

If you are publishing under a different package name, change the package metadata first. Do not publish a modified fork under someone else's package/project identity without permission.

For a private/internal package index, use that index's normal upload mechanism. For PyPI, `uv publish` or `twine upload` can be used after configuring credentials.

## Git release

Once validation and package inspection are complete:

```bash
git add -A
git commit -m "Release <version>"
git tag <version>
git push --follow-tags
```
