import assert from 'node:assert/strict';
import { readFile, readdir, stat } from 'node:fs/promises';
import { test } from 'node:test';

const origin = 'https://abdo-eid.github.io';
const base = '/finchvox/';
const dist = new URL('../dist/', import.meta.url);
const pages = [
  '',
  'start/overview/',
  'start/install/',
  'start/connect/',
  'start/replay/',
  'examples/livekit-agent/',
  'examples/docker/',
  'examples/terminal-recording/',
  'guides/python-install/',
  'guides/python-integration/',
  'guides/troubleshooting/',
  'reference/settings/',
  'reference/data-and-privacy/',
  'reference/pipecat/',
];

const getPage = (route) => readFile(new URL(`${route}index.html`, dist), 'utf8');

test('the full site is generated under the Pages project path', async () => {
  for (const route of pages) {
    const html = await getPage(route);
    assert.ok(html.includes(`href="${origin}${base}${route}"`), `canonical URL for ${route}`);
    assert.match(html, /<h1[\s>]/);
  }
  await stat(new URL('pagefind/pagefind.js', dist));
  const root = await readdir(dist);
  assert.ok(!root.some((entry) => /^(?:\.|private$|archive$|console-recordings$)/.test(entry)));
});

test('the quickstart has linear next-page navigation', async () => {
  const steps = pages.slice(1, 5);
  for (const [index, route] of steps.slice(0, -1).entries()) {
    const html = await getPage(route);
    assert.ok(html.includes(`href="${base}${steps[index + 1]}" rel="next"`), `next page for ${route}`);
  }
});

test('the quickstart starts with the published image and only the HTTP collector', async () => {
  const install = (await getPage('start/install/')).replace(/<[^>]*>/g, '');
  assert.ok(install.includes('docker pull ghcr.io/abdo-eid/finchvox:main'));
  assert.ok(install.includes('docker run'));
  assert.match(install, /127\.0\.0\.1:3000:3000/);
  assert.match(install, /finchvox-data:\/data/);
  assert.doesNotMatch(install, /uv tool install|4317:4317/);
  assert.match(await getPage('start/connect/'), /LIVEKIT_OBSERVABILITY_URL/);
  assert.match((await getPage('guides/python-install/')).replace(/<[^>]*>/g, ''), /uv tool install/);
});

test('the homepage links to all three entry points and the demo is labeled synthetic', async () => {
  const home = await getPage('');
  for (const route of ['start/overview/', 'examples/livekit-agent/', 'start/replay/']) {
    assert.ok(home.includes(`href="${base}${route}"`), route);
  }
  assert.match(await getPage('start/replay/'), /synthetic session/i);
});

test('internal links, anchors, and generated assets resolve under the project path', async () => {
  for (const route of pages) {
    const html = await getPage(route);
    const here = new URL(`${base}${route}`, origin);
    for (const [, raw] of html.matchAll(/\s(?:href|src)="([^"]+)"/g)) {
      const url = new URL(raw.replaceAll('&amp;', '&'), here);
      if (url.origin !== origin) continue;
      assert.ok(url.pathname.startsWith(base), `${route}: ${raw} escapes the Pages base`);
      const target = url.pathname.slice(base.length);
      if (!/\.[a-z\d]+$/i.test(target)) {
        const page = target && !target.endsWith('/') ? `${target}/` : target;
        const linked = await getPage(page);
        if (url.hash.length > 1) {
          const id = decodeURIComponent(url.hash.slice(1));
          assert.ok(linked.includes(`id="${id}"`), `${route}: missing anchor ${raw}`);
        }
      } else {
        await stat(new URL(target, dist));
      }
    }
  }
});
