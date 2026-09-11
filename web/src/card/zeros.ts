/**
 * FR-017 and required test **E11**: which zero a tax of `0.00` is.
 *
 * Two different claims wear the same figure. An **exempt** class charged nothing and cites the
 * provision that exempts it; a line **no rule ran on** — a purchase — has a zero resting on no
 * source at all. A reader who cannot tell them apart cannot tell a tax-free instrument from an
 * unmodelled one, which is the gap this required test has named since feature 001.
 *
 * Discriminated on whether the amount **cites** something, never on the amount alone.
 */
import type { Money } from "@/api/shapes";

export type TaxZero =
  | { readonly tag: "charged" }
  | { readonly tag: "exempted"; readonly sources: Money["provenance"]["sources"] }
  | { readonly tag: "no-rule-ran" };

export function taxZero(amount: Money): TaxZero {
  if (amount.amount !== 0) return { tag: "charged" };
  const sources = amount.provenance.sources;
  return sources.length === 0 ? { tag: "no-rule-ran" } : { tag: "exempted", sources };
}
