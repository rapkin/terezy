/**
 * FR-025 to FR-027: one candidate's card — the waterfall, the timeline, and the provenance once.
 *
 * **The provenance is behind one disclosure and reachable in full.** A card's citations run to
 * more characters than its figures do, and eliding one to a fixed length would put the reader
 * back where this feature found him — holding a conclusion he cannot check.
 */
import type { CandidateProjection, SourceRef, TupleOutcome } from "@/api/shapes";
import { beliefsOf } from "@/answer/beliefs";
import { day, money as rendered } from "@/design/format";
import { marksOf } from "@/lib/provenance";
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
  const sources = allSources(projection, outcome);
  return (
    <Disclosure name="provenance" summary="what every figure here rests on" count={sources.length}>
      <ul className="space-y-2" data-provenance-list>
        {sources.map((source) => (
          <li key={source.id} data-source={source.id}>
            <p className="font-mono text-xs">{source.id}</p>
            <LongValue text={source.citation} />
            <p className="text-xs text-[var(--ink-muted)]">
              retrieved {day(source.retrieved_on)},{" "}
              {source.verified_on === null
                ? "never verified"
                : `verified ${day(source.verified_on)}`}
            </p>
          </li>
        ))}
      </ul>
    </Disclosure>
  );
}

/**
 * Every source behind any figure on this card, each once.
 *
 * **Sources rather than marks.** A mark is a claim — *unverified*, *stale* — and it belongs on
 * the figure it qualifies, where the slot renders it. A list of marks here would need one for a
 * source carrying neither, and there is no such mark to give it; each entry states the two dates
 * instead and lets the reader see which is missing.
 */
function allSources(
  projection: CandidateProjection,
  outcome: TupleOutcome,
): readonly SourceRef[] {
  const provenances = [
    outcome.provenance,
    projection.way_in.one_way.provenance,
    ...projection.releases.map((release) => release.way_out.provenance),
    ...projection.charges.map((charge) => charge.provenance),
    ...projection.flows.flatMap((flow) => [flow.gross.provenance, flow.tax.provenance]),
  ];
  const seen = new Map<string, SourceRef>();
  for (const provenance of provenances) {
    for (const source of provenance.sources) seen.set(source.id, source);
  }
  return [...seen.values()].sort((one, other) => one.id.localeCompare(other.id));
}
