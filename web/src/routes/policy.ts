import type { Answered } from "@/api/client";
import type { CitationPolicy } from "@/api/shapes";
import { isRegistry } from "@/lib/narrow";

/**
 * The citation policy the registry states for one category (FR-013, OB-6).
 *
 * Read from the registry rather than from the record, because the exemption is a property of the
 * directory and 020 states it there. Absent where the registry has not been read yet: an absent
 * policy renders nothing, and a policy that says *exempt* renders the exemption with its reason.
 */
export function policyIn(answered: Answered | undefined, category: string): CitationPolicy | undefined {
  if (answered === undefined || answered.tag !== "body" || !isRegistry(answered.body)) {
    return undefined;
  }
  return answered.body.categories.find((summary) => summary.category === category)?.citations;
}
