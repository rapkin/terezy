import type { Comparison } from "@/api/shapes";
import { keyLabel } from "@/answer/keys";
import { count, day, money, rate } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "./Disclosure";
import { TupleTerms } from "./TupleTerms";

/**
 * FR-012: every ranked row, with all five terms, the benchmark row marked in **text**, and each
 * tie group shown as a group.
 *
 * `benchmark`, `beats_benchmark` and `ties` are indices into `ranked` — the API's own ordering
 * and the API's own grouping. Nothing here sorts, and nothing here decides what ties.
 */
export function FullRanking({ comparison }: { comparison: Comparison }) {
  const ties = new Map<number, number>();
  comparison.ties.forEach((group, at) => {
    for (const member of group) ties.set(member, at);
  });
  return (
    <Disclosure
      name="full-ranking"
      count={comparison.ranked.length}
      summary="the whole ranking, in the API's order"
    >
      <ol className="space-y-2" data-ranking>
        {comparison.ranked.map((outcome, at) => {
          const tie = ties.get(at);
          return (
            <li
              key={keyLabel(outcome.key)}
              data-ranked-at={String(at)}
              data-benchmark-row={at === comparison.benchmark ? "yes" : undefined}
              className={
                at === comparison.benchmark
                  ? "rounded border border-[var(--accent)] bg-[var(--surface-raised)] p-2"
                  : "p-2"
              }
            >
              <div className="text-xs">
                {at === comparison.benchmark ? (
                  <strong data-benchmark-text>the benchmark — </strong>
                ) : null}
                {comparison.beats_benchmark.includes(at) ? (
                  <span data-beats-benchmark>beats the benchmark — </span>
                ) : null}
                {tie === undefined ? null : (
                  <span data-tie-group={String(tie)}>tie group {count(tie + 1)} — </span>
                )}
                <FigureSlot
                  state={{
                    kind: "marked",
                    figure: money(outcome.reaches),
                    marks: marksOf(outcome.reaches.provenance, outcome.staleness),
                  }}
                />{" "}
                by <FigureSlot state={{ kind: "value", figure: day(outcome.span.end) }} />
                {outcome.implied_rate.tag === "rates.NominalRate" ? (
                  <>
                    {" at "}
                    <FigureSlot
                      state={{
                        kind: "marked",
                        figure: rate(outcome.implied_rate),
                        marks: marksOf(outcome.provenance, outcome.staleness),
                      }}
                    />
                  </>
                ) : (
                  <FigureSlot
                    state={{
                      kind: "refused-in-answer",
                      tag: outcome.implied_rate.tag,
                      reason: outcome.implied_rate.reason,
                    }}
                  />
                )}
              </div>
              <TupleTerms term={outcome.key} />
            </li>
          );
        })}
      </ol>
    </Disclosure>
  );
}
