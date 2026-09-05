# Dependencies: the concrete list, and where each one sits

**Feature**: `021-web-declared-data` | **Plan**: [../plan.md](../plan.md)

**The network-behaviour argument lives in the spec's own *Dependencies added* table and is not
copied here** — one fact, one place. What that table does not carry, and what an implementer needs
before writing `package.json`, is: the concrete package name, which section it goes in, and the
one column FR-037 actually gates on.

**FR-037's gate is the last column.** *"A dependency that makes a request at **run** time is
refused rather than configured off."* Every row below reads **no**, and a row that could not would
not be in the list.

## `dependencies` — shipped in the bundle

| Package | What it is | Run-time egress |
|---|---|---|
| `react`, `react-dom` | the renderer | no |
| `@tanstack/react-router` | routing, and the typed search-parameter validation FR-020 and FR-027 rest on | no |
| `@tanstack/react-query` | all server state — caching, retry and staleness of a **request**, in one place | no |
| `openapi-fetch` | a typed wrapper over `fetch`; every request is the app's own origin | no |
| `recharts` | the two charts | no |
| Radix UI primitives | what the shadcn components are built on; arrive as shadcn components are copied in | no |
| `class-variance-authority`, `clsx`, `tailwind-merge` | class composition for those components | no |
| the icon set | icons are **components**, never fetched sprites | no |

**Not a dependency at all: the fonts.** They are committed under `web/public/fonts/` and served
from the app's own origin (FR-035). A Google Fonts `<link>` would be an absolute URL in the HTML
and would fail FR-036's check on the first run — which is the check working.

**Not a runtime dependency: shadcn/ui.** Its CLI fetches component source at **authoring** time and
the result is committed as owned code, reviewed in git. What ends up in `dependencies` is the
Radix and class-composition rows above, and nothing named `shadcn`.

## `devDependencies` — build, test and tooling

| Package | What it is | Run-time egress |
|---|---|---|
| `typescript` | the typechecker FR-004 and FR-005 are enforced by | no |
| `vite`, `@vitejs/plugin-react` | dev server (proxying `/api` — never a third party) and build | no |
| Tailwind CSS and its Vite plugin | CSS generated at **build** time; the CDN script build is not used ([research D10](../research.md), risk R6 on the config shape) | no |
| `openapi-typescript` | reads the OpenAPI document **from the local filesystem**, not from a URL, and emits `schema.d.ts` | no |
| `vitest`, `@testing-library/react`, `jsdom` | the unit suite | no |
| `msw` | intercepts in-process for Node tests; where the browser worker is used its file is **generated into the repository** rather than fetched | no |
| `@playwright/test` | install downloads browser binaries — the one entry with real install-time egress, cached and outside the test run. The tests run with no network reachable (FR-045) | no |
| `@axe-core/playwright` | FR-043's accessibility pass, over every route in **both** themes | no |
| `eslint` and the TypeScript ESLint packages | the lint job: FR-004's no-`default`-arm rule (risk **R1**) and FR-021a's one-clock rule | no |
| the TanStack Router plugin or CLI, if the file-based router is used | generates the route tree (risk **R4**) | no |

## Install-time egress, stated once

Three sources, all at install or build and none at run: the package registry (any package
manager), Playwright's browser binaries, and the container base images — **pinned by digest**, and
reached by nothing at run time.

## What makes the list a gate rather than a list

- **FR-050**: the production build installs **frozen from the lockfile** and fails rather than
  resolve a version the lockfile does not name. A build that can pick a different dependency than
  CI typechecked is a build whose gates prove nothing.
- **FR-036**: the absolute-URL check over the built output is what catches a dependency that
  reaches somewhere at run time **despite** its row here — because this table is a review and that
  check is a machine.
- **No version is pinned in this plan.** The lockfile is the record, written by the scaffold task.
