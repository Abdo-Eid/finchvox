import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

export default defineConfig({
  site: 'https://abdo-eid.github.io',
  base: '/finchvox',
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'Finchvox Docs',
      description: 'Replay and debug LiveKit agent sessions on your own machine.',
      logo: { src: './src/assets/finchvox-mark.svg' },
      favicon: '/favicon.svg',
      social: [{ icon: 'github', label: 'GitHub', href: 'https://github.com/Abdo-Eid/finchvox' }],
      editLink: { baseUrl: 'https://github.com/Abdo-Eid/finchvox/edit/main/docs-site/' },
      customCss: ['./src/styles/finchvox.css'],
      components: { Hero: './src/components/HomeHero.astro' },
      sidebar: [
        {
          label: 'Get started',
          items: ['start/overview', 'start/install', 'start/connect', 'start/replay'],
        },
        {
          label: 'Examples',
          items: ['examples/livekit-agent', 'examples/docker', 'examples/terminal-recording'],
        },
        {
          label: 'Guides',
          items: ['guides/python-install', 'guides/python-integration', 'guides/troubleshooting'],
        },
        {
          label: 'Reference',
          items: ['reference/settings', 'reference/data-and-privacy', 'reference/pipecat'],
        },
      ],
    }),
  ],
});
