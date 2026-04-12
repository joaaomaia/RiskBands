import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

const repoOwner = 'joaaomaia';
const repoName = 'RiskBands';
const docsSiteUrl = process.env.DOCS_SITE_URL ?? `https://${repoOwner}.github.io`;
const docsBasePath =
  process.env.DOCS_BASE_PATH ?? (process.env.GITHUB_ACTIONS ? `/${repoName}` : '/');
const docsBasePathForMeta = docsBasePath === '/' ? '' : docsBasePath;
const socialPreviewUrl = `${docsSiteUrl}${docsBasePathForMeta}/og/riskbands-social-preview.png`;

export default defineConfig({
  site: docsSiteUrl,
  base: docsBasePath,
  output: 'static',
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'RiskBands',
      description:
        'Documentação oficial do RiskBands para binning com robustez temporal em risco de crédito, PD e scorecards.',
      favicon: '/favicon.svg',
      logo: {
        light: './src/assets/riskbands-light.svg',
        dark: './src/assets/riskbands-dark.svg',
        alt: 'RiskBands',
      },
      titleDelimiter: '-',
      locales: {
        root: {
          label: 'Português (Brasil)',
          lang: 'pt-BR',
        },
      },
      lastUpdated: true,
      social: [
        {
          icon: 'github',
          label: 'GitHub',
          href: 'https://github.com/joaaomaia/RiskBands',
        },
      ],
      editLink: {
        baseUrl: 'https://github.com/joaaomaia/RiskBands/edit/master/docs-site/',
      },
      customCss: ['./src/styles/custom.css'],
      head: [
        {
          tag: 'meta',
          attrs: {
            name: 'theme-color',
            content: '#0f6b59',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:site_name',
            content: 'RiskBands',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:type',
            content: 'website',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image',
            content: socialPreviewUrl,
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image:alt',
            content:
              'RiskBands: binning com robustez temporal para risco de crédito, PD e scorecards.',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image:width',
            content: '1280',
          },
        },
        {
          tag: 'meta',
          attrs: {
            property: 'og:image:height',
            content: '640',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'twitter:card',
            content: 'summary_large_image',
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'twitter:image',
            content: socialPreviewUrl,
          },
        },
        {
          tag: 'meta',
          attrs: {
            name: 'twitter:image:alt',
            content:
              'RiskBands: binning com robustez temporal para risco de crédito, PD e scorecards.',
          },
        },
      ],
      sidebar: [
        {
          label: 'Porta técnica',
          items: [
            { label: 'Instalação', link: '/technical/installation/' },
            { label: 'Quickstart', link: '/technical/quickstart/' },
            { label: 'Visão geral da API', link: '/technical/api-overview/' },
            { label: 'Exemplos', link: '/technical/examples/' },
          ],
        },
        {
          label: 'Porta metodológica',
          items: [
            { label: 'Por que RiskBands', link: '/methodology/why-riskbands/' },
            {
              label: 'Por que não usar apenas OptimalBinning',
              link: '/methodology/why-not-only-optimal-binning/',
            },
            { label: 'Benchmark PD vintage', link: '/methodology/pd-vintage-benchmark/' },
            { label: 'Como ler os gráficos', link: '/methodology/how-to-read-the-charts/' },
            {
              label: 'Robustez temporal em risco de crédito',
              link: '/methodology/temporal-robustness-in-credit-risk/',
            },
          ],
        },
        {
          label: 'Projeto',
          items: [
            { label: 'Release Notes', link: '/reference/release-notes/' },
            { label: 'Publicações', link: '/reference/publications/' },
            { label: 'Desenvolvimento', link: '/project/development/' },
          ],
        },
      ],
    }),
  ],
});
