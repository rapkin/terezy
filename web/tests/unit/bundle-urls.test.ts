import { describe, expect, it } from "vitest";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unlistedUrls } from "../../tools/check-bundle-urls.mjs";

/**
 * The checker itself, against a fixture bundle.
 *
 * A checker that passes on everything is green for the wrong reason, and this is the only test
 * that can tell the difference -- the real build passing says nothing about whether the check
 * can fail.
 */
function bundleContaining(body: string): string {
  const root = mkdtempSync(join(tmpdir(), "terezy-bundle-"));
  mkdirSync(join(root, "assets"), { recursive: true });
  writeFileSync(join(root, "assets", "index.js"), body, "utf8");
  return root;
}

describe("the bundle-URL check", () => {
  it("fails on an absolute URL nobody listed", () => {
    const found = unlistedUrls(bundleContaining('fetch("https://cdn.example.com/telemetry.js");'));
    expect(found.map((held) => held.url)).toEqual(["https://cdn.example.com/telemetry.js"]);
  });

  it("passes an absolute URL that is listed with its reason", () => {
    expect(unlistedUrls(bundleContaining('el.setAttribute("xmlns", "http://www.w3.org/2000/svg");'))).toEqual([]);
  });

  it("passes a bundle whose only URLs are relative", () => {
    expect(unlistedUrls(bundleContaining('fetch("/api/registry?as_of=2026-09-05");'))).toEqual([]);
  });

  it("catches a websocket as well as a fetch", () => {
    const found = unlistedUrls(bundleContaining('new WebSocket("wss://telemetry.example.com/s");'));
    expect(found).toHaveLength(1);
  });
});
