# RiskBands docs i18n strategy: pt-BR + English

## Product decision

RiskBands documentation uses pt-BR as the default language and English as the
secondary language.

- pt-BR remains at the current unprefixed URLs.
- English lives under `/en/`.
- Existing pt-BR URLs must not be moved to `/pt-br/`.
- The current sprint is docs-only and is not a release announcement.

## Route strategy

The Starlight configuration uses a root locale for pt-BR:

```js
locales: {
  root: {
    label: 'Português (Brasil)',
    lang: 'pt-BR',
  },
  en: {
    label: 'English',
    lang: 'en',
  },
}
```

Examples:

| pt-BR route | English route |
| --- | --- |
| `/` | `/en/` |
| `/technical/quickstart/` | `/en/technical/quickstart/` |
| `/technical/missing-policy/` | `/en/technical/missing-policy/` |
| `/reference/release-notes/` | `/en/reference/release-notes/` |

## Pages translated in this sprint

Priority pages translated:

- `index`
- `technical/installation`
- `technical/quickstart`
- `technical/api-overview`
- `technical/missing-policy`
- `technical/outputs`
- `technical/score-strategy`
- `technical/examples`
- `reference/release-notes`

Optional methodology pages also translated:

- `methodology/why-riskbands`
- `methodology/why-not-only-optimal-binning`
- `methodology/temporal-robustness-in-credit-risk`

## Pages still in translation backlog

These pages currently have English backlog notice stubs under `/en/`, but still
need full translation:

- `technical/audit-and-plots`
- `technical/optuna`
- `methodology/pd-vintage-benchmark`
- `methodology/how-to-read-the-charts`
- `reference/after-v1-0`
- `reference/publications`
- `project/development`

The stubs prevent untranslated pt-BR fallback content from being indexed as
English while keeping the `/en/` route structure complete.

## How to add a new page in both languages

1. Add or update the pt-BR page at the current unprefixed slug, for example:

   ```text
   docs-site/src/content/docs/technical/new-page.md
   ```

2. Add the English equivalent with the same slug under `en/`:

   ```text
   docs-site/src/content/docs/en/technical/new-page.md
   ```

3. If the page is included in the sidebar, add or update the sidebar item in
   `docs-site/astro.config.mjs` using `slug`, not a hard-coded absolute `link`.

4. Add `translations` for sidebar labels when the default label is pt-BR.

## Link rules

- In pt-BR pages, preserve current relative links whenever possible.
- In EN pages, prefer relative links to English pages, for example
  `../missing-policy/` or `./technical/quickstart/`.
- When an EN backlog stub links to the full pt-BR page, use a relative path that
  escapes `/en/`, for example `../../../technical/optuna/`.
- Avoid hard-coded root links like `/technical/...` in Markdown content because
  they can bypass a GitHub Pages base path.
- Preserve API identifiers and configuration values exactly, including:
  `missing_policy`, `standard`, `separate_bin`, `forbid`, `RiskBands`, and
  `Binner`.

## Build validation

From the repository root:

```bash
npm --prefix docs-site run build
```

If dependencies are missing:

```bash
npm --prefix docs-site ci
npm --prefix docs-site run build
```

After a successful build, verify:

- pt-BR routes still exist without a locale prefix.
- `/en/` routes exist for translated pages.
- `docs-site/dist/sitemap-index.xml` and `docs-site/dist/sitemap-0.xml` exist.
- `docs-site/dist/pagefind/` contains metadata for both `en` and `pt-br`.

## Next steps

- Fully translate backlog notice pages.
- Review EN terminology for credit-risk consistency.
- Consider adding focused link-check automation for `docs-site/dist/`.
- Keep release announcements separate from docs i18n work.
