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

## Fresh Android screenshots

The Go Mode repository owns the emulator and scenarios. Generate its Android captures first, then import the ones this site references:

```bash
pnpm run screenshots --source ../gomode/e2e/screenshots/android
```

The importer copies only the images `public/index.html` references and validates their WebP headers and dimensions before publishing. Publication uses two directory renames with a brief gap; a persistent previous catalog makes interruption recoverable. Unix imports serialize writers using an advisory lock. After a forced exit, rerun `--source` to recover before validating; `--check` reports pending recovery and never writes files. Site builds do not download browsers, build an APK, or require a sibling checkout.

## Deployment

The new asset-only Worker is named **gomode-website**. It intentionally differs from the old `gomode-dev` / `gomodev-dev` waitlist Worker so publishing this site does not migrate or delete its Durable Object namespaces or saved submissions.

Before the first publication, connect this repository’s `main` branch to `gomode-website` in Cloudflare Workers Builds. Use:

- Build command: `pnpm install --frozen-lockfile && pnpm run build`
- Deploy command: `pnpm exec wrangler deploy`
- Preview command: `pnpm exec wrangler versions upload`
- Build variable: `SKIP_DEPENDENCY_INSTALL=1`

The Cloudflare account must own the `gomode.dev` zone. If the domain is attached to the old Worker, remove only that custom-domain attachment before assigning it to `gomode-website`; keep the old Worker and its Durable Objects until the stored submissions have been exported and deliberately retired. Do not add a deletion migration to publish this site.

`wrangler.jsonc` owns the custom domain and asset routing. `pnpm run build` performs a local dry run and does not publish. `pnpm run deploy` publishes after checks; run it only when publication is intended.

[Cloudflare static assets](https://developers.cloudflare.com/workers/static-assets/) and [custom domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/) describe the hosting contract.
