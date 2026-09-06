import type { Belief } from "@/answer/beliefs";
import { Disclosure } from "./Disclosure";

/**
 * FR-018, FR-020 and FR-024, which are one block on the screen because they are one claim about
 * every card below: what they all rest on, what they all believe, and what the rate is measured
 * on.
 *
 * FR-018's sentence is not decoration. Without it the rate is non-monotonic against *money back*
 * across rows of equal span — a smaller amount can carry a larger rate because less of the money
 * was invested — and a reader takes the disagreement for an error.
 */
export function SharedAssumptions({
  shared,
  beliefs,
}: {
  shared: readonly string[];
  beliefs: readonly Belief[];
}) {
  return (
    <section className="space-y-2 rounded border border-[var(--border)] p-3" data-shared>
      <h2 className="text-sm font-semibold">what every candidate below rests on</h2>
      <p className="text-xs" data-rate-scope>
        a rate is measured on the money actually invested, not on the whole amount asked about.
      </p>
      {beliefs.map((belief) => (
        <BeliefLine key={belief.id} belief={belief} />
      ))}
      {shared.length === 0 ? (
        <p className="text-xs text-[var(--ink-muted)]" data-shared-none>
          nothing is shared by every candidate: each one states its own assumptions on its card.
        </p>
      ) : (
        <Disclosure name="shared-assumptions" summary="stated once, for all of them" count={shared.length}>
          <ul className="ml-4 list-disc space-y-1" data-served-text="shared">
            {shared.map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        </Disclosure>
      )}
    </section>
  );
}

/** FR-024: once per screen per distinct belief id, with the full statement one interaction away. */
export function BeliefLine({ belief }: { belief: Belief }) {
  return (
    <div data-belief={belief.id}>
      <Disclosure name="belief" summary={<span>this rests on the belief {belief.id}</span>}>
        <p data-served-text="belief">{belief.rationale}</p>
      </Disclosure>
    </div>
  );
}
