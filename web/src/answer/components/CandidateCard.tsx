import type { Indistinguishable, TupleOutcome } from "@/api/shapes";
import { beliefsOf, withoutBeliefs } from "@/answer/beliefs";
import { sameTuple } from "@/answer/keys";
import { separatingBadge } from "@/answer/separating";
import { beyondShared } from "@/answer/assumptions";
import type { KindReading } from "@/answer/instrument-kind";
import { classLabel } from "@/answer/instrument-kind";
import { day, rate } from "@/design/format";
import { KindTile } from "@/design/KindTile";
import { marksOf } from "@/lib/provenance";
import { Badge } from "@/components/ui/badge";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { WhyLink } from "@/card/components/WhyLink";
import { Disclosure } from "./Disclosure";
import { MoneyBack } from "./MoneyBack";
import { SeparatingBadge } from "./SeparatingBadge";

/**
 * FR-015: the kind tile and the id, *money back*, *all of it by*, the rate, one separating
 * badge, and — where the member is indistinguishable from others — those others named.
 *
 * The last is the honest form of *these score within noise*: without it a column of cards reads
 * as an ordering, which is the false optimum Principle I exists to refuse.
 */
export function CandidateCard({
  outcome,
  reading,
  shared,
  indistinguishable,
  questionId,
}: {
  outcome: TupleOutcome;
  reading: KindReading;
  shared: readonly string[];
  indistinguishable: Indistinguishable | undefined;
  questionId: string;
}) {
  // The belief's own sentence is folded into the once-per-screen line, so what is left here is
  // what this member rests on and nothing else (FR-024).
  const own = withoutBeliefs(beyondShared(outcome, shared), beliefsOf(outcome));
  const className = classLabel(reading);
  return (
    <article
      className="space-y-2 rounded border border-[var(--border)] bg-[var(--surface-raised)] p-3"
      data-candidate={outcome.key.instrument_id}
    >
      <header className="flex flex-wrap items-center gap-2">
        <KindOf reading={reading} />
        <span className="font-mono text-sm">{outcome.key.instrument_id}</span>
        {className === null ? null : (
          <span className="text-xs text-[var(--ink-muted)]" data-instrument-class>
            {className}
          </span>
        )}
      </header>

      <MoneyBack outcome={outcome} />

      <WhyLink outcome={outcome} questionId={questionId} />

      <Span span={outcome.span} />

      <div className="text-xs">
        <span className="text-[var(--ink-muted)]">rate </span>
        <Rate outcome={outcome} />
      </div>

      <SeparatingBadge badge={separatingBadge(outcome)} />

      {beliefsOf(outcome).map((belief) => (
        // FR-024: a mark naming the belief, never a copy of its statement — the statement is on
        // the screen once.
        <Badge key={belief.id} tone="assume" data-belief-mark={belief.id}>
          rests on {belief.id}
        </Badge>
      ))}

      {indistinguishable === undefined ? null : (
        <p className="text-xs" data-indistinguishable>
          within the declared band of{" "}
          {indistinguishable.neighbours.map((held) => held.instrument_id).join(", ")} — these score
          the same, and the order they appear in is not a ranking
        </p>
      )}

      {own.length === 0 ? null : (
        <Disclosure name="own-assumptions" summary="what only this one rests on" count={own.length}>
          <ul className="ml-4 list-disc space-y-1" data-served-text="rests-on">
            {own.map((sentence) => (
              <li key={sentence}>{sentence}</li>
            ))}
          </ul>
        </Disclosure>
      )}
    </article>
  );
}

/**
 * The span the rate was measured over, as the two dates the API sent.
 *
 * **Not** their difference in days. A length is a figure the API does not send, and FR-009's
 * permitted lookups — a key-equality join, a count of a served population, a grouping by typed
 * fields — do not cover subtracting one served date from another. The comparability predicate
 * computes the same difference and is allowed to, because it yields a boolean and never reaches
 * the page. OB-16 is what would put the length here.
 */
function Span({ span }: { span: TupleOutcome["span"] }) {
  return (
    <p className="text-xs text-[var(--ink-muted)]" data-span={`${span.start}/${span.end}`}>
      measured over {day(span.start)} to {day(span.end)}
    </p>
  );
}

/** FR-002/FR-006: the tile, or the state saying why the instrument read gave no kind. */
function KindOf({ reading }: { reading: KindReading }) {
  switch (reading.tag) {
    case "read":
      return <KindTile kind={reading.kind} />;
    case "reading":
      return (
        <span className="text-xs text-[var(--ink-muted)]" data-kind-state="reading">
          reading what kind this is…
        </span>
      );
    case "not-read":
      return (
        <Badge tone="warn" data-kind-state="not-read">
          kind unread: {reading.why}
        </Badge>
      );
  }
}

/**
 * OB-19: `implied_rate` carries no provenance of its own, so it wears the **outcome's** merged
 * mark and the slot says which.
 */
function Rate({ outcome }: { outcome: TupleOutcome }) {
  const held = outcome.implied_rate;
  if (held.tag !== "rates.NominalRate") {
    return (
      <FigureSlot
        state={{
          kind: "refused-in-answer",
          tag: held.tag,
          reason: held.reason,
          detail: <p className="mt-1 text-xs">what is missing: {held.missing}</p>,
        }}
      />
    );
  }
  return (
    <>
      <FigureSlot
        state={{
          kind: "marked",
          figure: rate(held),
          marks: marksOf(outcome.provenance, outcome.staleness),
        }}
      />
      <span className="text-[var(--ink-muted)]"> (the outcome&apos;s own marks)</span>
    </>
  );
}

/** The `indistinguishable` entry for this key, where the pass placed one. */
export function indistinguishableFor(
  outcome: TupleOutcome,
  members: readonly Indistinguishable[],
): Indistinguishable | undefined {
  return members.find((held) => sameTuple(held.key, outcome.key));
}
