import { describe, expect, it } from "vitest";
import { spawnSync } from "node:child_process";
import { cpSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { openapiDocument, WEB } from "../../tools/openapi.mjs";

/**
 * SC-003, demonstrated rather than asserted about.
 *
 * A member added to a **copy** of the OpenAPI document turns the build red at the site that does
 * not handle it. This is the only one of FR-004's three mechanisms that cannot pass vacuously,
 * and it is what proves `assertNever` and the lint rule are wired rather than merely present.
 *
 * The copy lives under `web/` so module resolution still walks up to `web/node_modules`; a temp
 * directory elsewhere would fail to resolve React and be red for the wrong reason.
 */
const SCRATCH = join(WEB, ".union-widening");

async function widened(): Promise<string> {
  const document: unknown = JSON.parse(await openapiDocument());
  if (typeof document !== "object" || document === null) throw new Error("not a document");
  const held: Record<string, unknown> = { ...document };
  const components: Record<string, unknown> = { ...(held["components"] ?? {}) };
  const schemas: Record<string, unknown> = { ...(components["schemas"] ?? {}) };
  schemas["envelopes_RefusalTheClientHasNoArmFor"] = {
    additionalProperties: false,
    type: "object",
    title: "envelopes_RefusalTheClientHasNoArmFor",
    required: ["tag", "reason"],
    properties: {
      tag: { const: "envelopes.RefusalTheClientHasNoArmFor", title: "Tag", type: "string" },
      reason: { title: "Reason", type: "string" },
    },
  };
  const window: Record<string, unknown> = { ...(schemas["envelopes_WindowOfCpi"] ?? {}) };
  const properties: Record<string, unknown> = { ...(window["properties"] ?? {}) };
  const result: Record<string, unknown> = { ...(properties["result"] ?? {}) };
  const members: unknown[] = Array.isArray(result["oneOf"]) ? [...result["oneOf"]] : [];
  members.push({ $ref: "#/components/schemas/envelopes_RefusalTheClientHasNoArmFor" });
  const discriminator: Record<string, unknown> = { ...(result["discriminator"] ?? {}) };
  const mapping: Record<string, unknown> = { ...(discriminator["mapping"] ?? {}) };
  mapping["envelopes.RefusalTheClientHasNoArmFor"] =
    "#/components/schemas/envelopes_RefusalTheClientHasNoArmFor";
  result["oneOf"] = members;
  result["discriminator"] = { ...discriminator, mapping };
  properties["result"] = result;
  window["properties"] = properties;
  schemas["envelopes_WindowOfCpi"] = window;
  components["schemas"] = schemas;
  held["components"] = components;
  return JSON.stringify(held);
}

function typecheck(): { status: number | null; output: string } {
  const run = spawnSync(join(WEB, "node_modules", ".bin", "tsc"), ["--noEmit", "-p", "tsconfig.json"], {
    cwd: SCRATCH,
    encoding: "utf8",
  });
  return { status: run.status, output: (run.stdout ?? "") + (run.stderr ?? "") };
}

describe("adding a member to a closed union turns the build red", () => {
  it("fails the typecheck at the site that does not handle it", async () => {
    rmSync(SCRATCH, { recursive: true, force: true });
    mkdirSync(SCRATCH, { recursive: true });
    try {
      cpSync(join(WEB, "src"), join(SCRATCH, "src"), { recursive: true });
      writeFileSync(join(SCRATCH, "widened.json"), await widened(), "utf8");
      const generated = spawnSync(
        join(WEB, "node_modules", ".bin", "openapi-typescript"),
        ["widened.json", "--output", join("src", "api", "schema.d.ts")],
        { cwd: SCRATCH, encoding: "utf8" },
      );
      expect(generated.status).toBe(0);

      writeFileSync(
        join(SCRATCH, "tsconfig.json"),
        JSON.stringify({
          extends: "../tsconfig.json",
          compilerOptions: { baseUrl: ".", paths: { "@/*": ["./src/*"] } },
          include: ["src"],
        }),
        "utf8",
      );

      const red = typecheck();
      expect(red.status).not.toBe(0);
      expect(red.output).toContain("RefusalTheClientHasNoArmFor");
      expect(red.output).toContain("Refusal.tsx");
    } finally {
      rmSync(SCRATCH, { recursive: true, force: true });
    }
  }, 180_000);
});
