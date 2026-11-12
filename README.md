# gomode.dev

Static Go Mode product website deployed with Cloudflare Workers assets. No server runtime, secrets, waitlist, or persistent browser connection is needed.

```bash
pnpm install --frozen-lockfile
pnpm run fix
pnpm run verify
pnpm run build
pnpm run dev
```

## Browser acceptance

```bash
pnpm exec playwright install chromium
pnpm run test:browser
```

The suite checks desktop and mobile layout, keyboard navigation, image loading, runtime errors, and missing pages. To use a locally installed Chromium instead, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable. Browser evidence is written under ignored `test-results/`.

## Go Mode publishes the screenshots and favicon

The Go Mode repository owns the emulator, the scenarios, the launcher icon, and publication. Generate its Android captures, then publish the captures this site references and the favicon:

```bash
(cd ../gomode && uv run --locked python scripts/publish_screenshots.py ../gomode.dev)
(cd ../gomode && uv run --locked python scripts/publish_favicon.py ../gomode.dev)
```

`public/screenshots` then holds exactly the referenced captures; Git restores it if a copy is interrupted. `pnpm run verify` checks that the committed images match the page references. Site builds do not download browsers, build an APK, or require a sibling checkout.

## Deployment

The asset-only Worker is named **gomode-dev**. Connect this repository’s `main` branch to it in Cloudflare Workers Builds. Use:

- Build command: `pnpm install --frozen-lockfile && pnpm run build`
- Deploy command: `pnpm exec wrangler deploy`
- Preview command: `pnpm exec wrangler versions upload`
- Build variable: `SKIP_DEPENDENCY_INSTALL=1`

The Cloudflare account must own the `gomode.dev` zone.

`wrangler.jsonc` owns the custom domain and asset routing. `pnpm run build` performs a local dry run and does not publish. `pnpm run deploy` publishes after checks; run it only when publication is intended.

[Cloudflare static assets](https://developers.cloudflare.com/workers/static-assets/) and [custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/) describe the hosting contract.

## Brand

The palette takes its blues from the Go Mode launcher icon. Text and brand colors meet WCAG AA contrast on the paper and surface colors. docs.gomode.dev mirrors these values.

| Role         | Light     | Dark      |
| ------------ | --------- | --------- |
| Brand        | `#1d6a96` | `#5cc3e6` |
| Brand strong | `#174878` | `#8fd6ee` |
| Paper        | `#f4f8fb` | `#0d1a2b` |
| Surface      | `#e4edf3` | `#172a40` |
| Ink          | `#0d2148` | `#eaf2f8` |
| Muted        | `#47596b` | `#bccddb` |
| Line         | `#c4d3df` | —         |
| Focus        | `#b45309` | —         |
