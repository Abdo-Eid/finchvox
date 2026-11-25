# Finchvox Docs

A static Astro Starlight site. It is built independently of the Python app and the UI in `../ui/`. Pages never connect to a local Finchvox server or include real session data.

## Work on the site

Use Node.js 24 LTS and npm. From this directory:

```sh
npm ci
npm run dev
```

Open `http://localhost:4321/finchvox/`. Write guides under `src/content/docs/` as Markdown; use MDX (Markdown with components) for snippets and the replay illustration. `astro.config.mjs` defines the sidebar order, which also drives Previous and Next. Use relative links between Markdown pages and `import.meta.env.BASE_URL` in components so links work under the GitHub Pages project path.

Use the existing runnable examples as the source of truth, and use only synthetic data for public demos and screenshots. The LiveKit example page pulls in `examples/livekit/agent.py` at build time rather than maintaining a duplicate snippet.

## Check and preview the build

```sh
npm test
npm run preview
```

The test builds `dist/` and checks generated pages, the quickstart's Next links, internal URLs and anchors, and the search index. Test the real search using the production preview, not the dev server.

## Publish on GitHub Pages

In `Abdo-Eid/finchvox`, select **Settings → Pages → Build and deployment → Source → GitHub Actions**. The [docs workflow](../.github/workflows/docs.yml) builds pull requests that touch the site or its example source. It publishes only from `main` on `Abdo-Eid/finchvox`, on relevant pushes or a manual run. The expected site URL is `https://abdo-eid.github.io/finchvox/`.

Before advertising the docs URL, follow the [image publishing checklist](../docs/DOCKER.md#publishing-the-image) and verify the quickstart image pulls without signing in.

To use another repository or a custom domain, adjust `site` and `base` in `astro.config.mjs`, and update the deployment guard and URL assertions to match.
