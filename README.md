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
pnpm run test
```

The suite checks desktop and mobile layout, keyboard navigation, image loading, runtime errors, and missing pages. To use a locally installed Chromium instead, set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to its executable. Browser evidence is written under ignored `test-results/`.

## This site imports screenshots; Go Mode publishes the favicon

The Go Mode repository owns native Android captures and the launcher icon. This website owns screenshot import and host selection. caic and mddb own their real frontend captures. Refresh captures in their owning repository with `make screenshots-update`, then publish the captures this site references and the favicon:

```bash
uv run --locked python scripts/publish_screenshots.py
(cd ../gomode && uv run --locked python scripts/publish_favicon.py ../gomode.dev)
```

Importing screenshots requires sibling `gomode`, `caic`, and `mddb` checkouts. This site’s `scripts/publish_screenshots.py` maps each image to its owning suite; Go Mode does not depend on its host applications.

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
| Accent text  | `#a14a08` | —         |

Focus draws keyboard focus outlines, which need 3:1 contrast. Accent text is the darker amber for highlighted text, such as the Android voice panel's active tool name; it keeps 4.5:1 on the panel's tinted surface, where Focus does not.
