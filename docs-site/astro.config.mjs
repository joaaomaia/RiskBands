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
        en: {
          label: 'English',
          lang: 'en',
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
        baseUrl: 'https://github.com/joaaomaia/RiskBands/edit/main/docs-site/',
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
          translations: { en: 'Technical guide' },
          items: [
            { label: 'Instalação', translations: { en: 'Installation' }, slug: 'technical/installation' },
            { label: 'Quickstart', slug: 'technical/quickstart' },
            {
              label: 'Score e estratégias',
              translations: { en: 'Score and strategies' },
              slug: 'technical/score-strategy',
            },
            { label: 'Missing policy', slug: 'technical/missing-policy' },
            {
              label: 'Outputs e diagnóstico',
              translations: { en: 'Outputs and diagnostics' },
              slug: 'technical/outputs',
            },
            {
              label: 'Auditoria e plots',
              translations: { en: 'Audit and plots' },
              slug: 'technical/audit-and-plots',
            },
            { label: 'Optuna', slug: 'technical/optuna' },
            {
              label: 'Visão geral da API',
              translations: { en: 'API overview' },
              slug: 'technical/api-overview',
            },
            { label: 'Exemplos', translations: { en: 'Examples' }, slug: 'technical/examples' },
          ],
        },
        {
          label: 'Porta metodológica',
          translations: { en: 'Methodology' },
          items: [
            {
              label: 'Por que RiskBands',
              translations: { en: 'Why RiskBands' },
              slug: 'methodology/why-riskbands',
            },
            {
              label: 'Por que não usar apenas OptimalBinning',
              translations: { en: 'Why not only OptimalBinning' },
              slug: 'methodology/why-not-only-optimal-binning',
            },
            {
              label: 'Benchmark PD vintage',
              translations: { en: 'PD vintage benchmark' },
              slug: 'methodology/pd-vintage-benchmark',
            },
            {
              label: 'Como ler os gráficos',
              translations: { en: 'How to read the charts' },
              slug: 'methodology/how-to-read-the-charts',
            },
            {
              label: 'Robustez temporal em risco de crédito',
              translations: { en: 'Temporal robustness in credit risk' },
              slug: 'methodology/temporal-robustness-in-credit-risk',
            },
          ],
        },
        {
          label: 'Projeto',
          translations: { en: 'Project' },
          items: [
            { label: 'Release Notes', slug: 'reference/release-notes' },
            {
              label: 'Evolução após v1.0.0',
              translations: { en: 'Evolution after v1.0.0' },
              slug: 'reference/after-v1-0',
            },
            {
              label: 'Publicações',
              translations: { en: 'Publications' },
              slug: 'reference/publications',
            },
            {
              label: 'Desenvolvimento',
              translations: { en: 'Development' },
              slug: 'project/development',
            },
          ],
        },
      ],
    }),
  ],
});
