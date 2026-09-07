/**
 * FR-014: the condition and its consequence, and **no derived figure**.
 *
 * The span range the CLI composes is OB-16; a second client composing the same sentence is where
 * two readers get two answers. Each row states its own span instead.
 */
export function ComparabilityBanner() {
  return (
    <p
      role="note"
      data-comparability-banner
      className="rounded border border-[var(--warn-border)] bg-[var(--warn-surface)] p-2 text-xs text-[var(--warn-ink)]"
    >
      these rows were measured over spans of different length, and each rate is annualised over
      its own span — so the rates below are not comparable across rows. Each row states the span
      it was measured over.
    </p>
  );
}
