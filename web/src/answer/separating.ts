/**
 * FR-019: the badge that says what separates a member from its neighbours, from **typed** facts.
 *
 * Never from `separating.per_member[].rests_on`, which is a tuple of composed sentences and is
 * **empty on exactly the members that most need a badge**: measured 2026-09-07 across all three
 * fronts, every member sold at the window's end carries zero sentences and every member that ran
 * to its own end carries one — because what separates the first is the *absence* of the
 * continuation assumption the second has. A badge read off that list would be blank on four of
 * the twenty cards, and blank on the four the reader most needs told apart.
 */
import type { TupleOutcome } from "@/api/shapes";

type SoldEarly = NonNullable<TupleOutcome["sold_early"]>;

export type SeparatingBadge =
  | { readonly tag: "sold-at-the-end"; readonly on: string }
  | { readonly tag: "closed-by-its-own-terms" }
  | { readonly tag: "unlabelled"; readonly raw: string };

/**
 * The labels this client has, as a mapped type over the union it reads.
 *
 * A member added to `sold_early` leaves this one key short and the build red; the lookup below
 * is still by string, because a body arrives as `unknown` and a tag the types do not know about
 * must render raw rather than as nothing.
 */
const SOLD_EARLY_TAGS: { readonly [Tag in SoldEarly["tag"]]: true } = {
  "early_exit.SoldEarly": true,
};

export function separatingBadge(outcome: TupleOutcome): SeparatingBadge {
  const sold = outcome.sold_early;
  // Absent is a fact and not a gap: the position ran to its own end inside the window and the
  // proceeds sit as cash under the section's declared continuation assumption.
  if (sold === null) return { tag: "closed-by-its-own-terms" };
  if (!Object.hasOwn(SOLD_EARLY_TAGS, sold.tag)) return { tag: "unlabelled", raw: sold.tag };
  return { tag: "sold-at-the-end", on: sold.on };
}
