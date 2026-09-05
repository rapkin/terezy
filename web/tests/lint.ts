import { ESLint } from "eslint";
import { randomBytes } from "node:crypto";
import { rmSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { WEB } from "../tools/openapi.mjs";

/**
 * Lint one throwaway module **inside** `src/`.
 *
 * Inside, because a fixture outside `src/` is outside the rules being tested and the assertion
 * would then be green for a reason that has nothing to do with them. Written and removed per
 * call, because a fixture left in the tree would make the lint job permanently red.
 */
export async function messagesFor(source: string): Promise<readonly string[]> {
  const file = join(WEB, "src", `__lint-probe.${randomBytes(6).toString("hex")}.ts`);
  writeFileSync(file, source, "utf8");
  try {
    return await messagesIn(file);
  } finally {
    rmSync(file, { force: true });
  }
}

export async function messagesIn(file: string): Promise<readonly string[]> {
  const eslint = new ESLint({ cwd: WEB });
  const results = await eslint.lintFiles([file]);
  return results.flatMap((result) => result.messages.map((message) => message.message));
}
