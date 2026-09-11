/**
 * The named states this card can be in, and never a blank in any of them.
 *
 * Three shapes, and they are different facts: the endpoint's **two** refusals — a wrong URL
 * against a key from another answer (FR-011) — and a bar the arm states no flow for, which lives
 * in the body rather than in that list (FR-007, FR-016).
 */
import type { NotStated, ProjectionRefused } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";

/** What a reader should do about each refusal, which is the reason the two are separate. */
export function remedyFor(refusal: ProjectionRefused): string {
  switch (refusal.tag) {
    case "envelopes.CategoryHasNoSuchId":
      return "the URL names a question nobody declares — open one of the declared ones";
    case "card.NoSuchCandidate":
      // An empty list is the endpoint saying the **answer** refused, so it published no key at
      // all: telling that reader to reopen the answer sends him back to the same refusal.
      return refusal.evaluated_keys.length === 0
        ? "the question itself was not answered as of this date — the reason beside this is the answer's, and no candidate was evaluated to have a card"
        : "this key is from another answer, another date or another question — reopen the answer";
  }
  assertNever(refusal);
}

/** Whether a bar is an absence rather than a value. A zero is a value; an absence is not. */
export function isAbsence(state: unknown): state is NotStated {
  return (
    typeof state === "object" &&
    state !== null &&
    "tag" in state &&
    state.tag === "card.NotStated"
  );
}
