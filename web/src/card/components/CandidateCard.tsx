/**
 * FR-025 to FR-027: one candidate's card — the waterfall, the timeline, and the provenance once.
 *
 * **The provenance is behind one disclosure and reachable in full.** Measured on a sample card,
 * the served flows carry 25 538 characters of citation against 43 094 bytes of body; eliding one
 * to a fixed length would put the reader back where this feature found him. Every figure goes
 * through 026's one formatting module, so no unrounded float reaches the document.
 */
import type { CandidateProjection, TupleOutcome } from "@/api/shapes";
import { beliefsOf } from "@/answer/beliefs";
import { day, money as rendered } from "@/design/format";
import { marksOf, type Mark } from "@/lib/provenance";
import { Badge } from "@/components/ui/badge";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "@/answer/components/Disclosure";
import { LongValue } from "@/components/record/LongValue";
import { Attribution } from "./Attribution";
import { Timeline } from "./Timeline";
import { Waterfall } from "./Waterfall";

export function CandidateCard({
  projection,
  outcome,
}: {
  projection: CandidateProjection;
  outcome: TupleOutcome;
}) {
  return (
    <article className="space-y-4" data-card={projection.projection_key}>
      <header className="space-y-1">
        <h2 className="text-base font-semibold">
          why <span className="font-mono">{projection.instrument_id}</span> comes back with this
        </h2>
        <p className="text-sm">
          <span className="text-[var(--ink-muted)]">money back </span>
          <FigureSlot
            state={{
              kind: "marked",
              figure: rendered(outcome.reaches),
              marks: marksOf(outcome.reaches.provenance, outcome.staleness),
            }}
          />
          <span className="text-[var(--ink-muted)]">
            {" "}
            measured over {day(outcome.span.start)} to {day(outcome.span.end)}
          </span>
        </p>
        <Beliefs outcome={outcome} />
      </header>

      <Waterfall projection={projection} outcome={outcome} />
      <Attribution outcome={outcome} />
      <Timeline projection={projection} outcome={outcome} />
      <Sources projection={projection} outcome={outcome} />
    </article>
  );
}

/**
 * FR-026: the belief's own statement is on the answer screen once, so this names it and does not
 * repeat it. The bars leaning on it carry the mark.
 */
function Beliefs({ outcome }: { outcome: TupleOutcome }) {
  const beliefs = beliefsOf(outcome);
  if (beliefs.length === 0) return null;
  return (
    <p className="flex flex-wrap gap-1">
      {beliefs.map((belief) => (
        <Badge key={belief.id} tone="assume" data-belief-mark={belief.id}>
          rests on {belief.id}
        </Badge>
      ))}
    </p>
  );
}

/** Every source behind any figure on this card, once, in full, behind one disclosure. */
function Sources({
  projection,
  outcome,
}: {
  projection: CandidateProjection;
  outcome: TupleOutcome;
}) {
  const marks = allMarks(projection, outcome);
  return (
    <Disclosure name="provenance" summary="what every figure here rests on" count={marks.length}>
      <ul className="space-y-2" data-provenance-list>
        {marks.map((mark) => (
          <li key={mark.source.id} data-source={mark.source.id}>
            <p className="font-mono text-xs">{mark.source.id}</p>
            <LongValue text={mark.source.citation} />
            <p className="text-xs text-[var(--ink-muted)]">
              retrieved {day(mark.source.retrieved_on)},{" "}
              {mark.source.verified_on === null
                ? "never verified"
                : `verified ${day(mark.source.verified_on)}`}
            </p>
          </li>
        ))}
      </ul>
    </Disclosure>
  );
}

function allMarks(projection: CandidateProjection, outcome: TupleOutcome): readonly Mark[] {
  const provenances = [
    outcome.provenance,
    projection.way_in.one_way.provenance,
    ...projection.releases.map((release) => release.way_out.provenance),
    ...projection.charges.map((charge) => charge.provenance),
    ...projection.flows.flatMap((flow) => [flow.gross.provenance, flow.tax.provenance]),
  ];
  const seen = new Map<string, Mark>();
  for (const provenance of provenances) {
    for (const source of provenance.sources) {
      // Every source, marked or not: this list is what the card rests on, and a list of only the
      // unmarked ones would read as a clean bill of health for the rest.
      const held = marksOf({ ...provenance, sources: [source] }, outcome.staleness);
      seen.set(source.id, held[0] ?? { tag: "unverified", source });
    }
  }
  return [...seen.values()].sort((one, other) => one.source.id.localeCompare(other.source.id));
}
