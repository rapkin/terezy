import type { Page } from "@playwright/test";
import { BASE_URL } from "./playwright.config";

export const AS_OF = "2026-09-05";

/**
 * FR-045: nothing but this application's own origin is reachable.
 *
 * Job-level network isolation is the belt; this is the load-bearing strap. A page that tried to
 * reach a CDN fails the test it is in rather than merely being slow, and the failure names the
 * URL it tried.
 *
 * The predicate excludes this application's own origin so those requests are never intercepted
 * at all: routing them through the driver copies every response body across the wire twice, and
 * the registry read is megabytes.
 */
export async function offline(page: Page): Promise<void> {
  await page.route(
    (url) => !url.href.startsWith(BASE_URL),
    async (route) => {
      await route.abort("blockedbyclient");
    },
  );
}
