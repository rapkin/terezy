import type {
  BenchmarkStanding as Standing,
  Comparison,
  HorizonSection,
  RefusedTuple,
  TupleOutcome,
} from "@/api/shapes";
import type { KindReading } from "@/answer/instrument-kind";
import { spansDiffer } from "@/answer/comparability";
import { groupNoCandidates, groupRefusals } from "@/answer/grouping";
import { joinToOutcome, placeable } from "@/answer/join";
import { listKey } from "@/answer/keys";
import { count, day } from "@/design/format";
import { assertNever } from "@/lib/exhaustive";
import { CandidateCard, indistinguishableFor } from "./CandidateCard";
import { ComparabilityBanner } from "./ComparabilityBanner";
import { Disclosure } from "./Disclosure";
import { FullRanking } from "./FullRanking";
import { Population } from "./Population";
import { RefusalGroup } from "./RefusalGroup";
import { TypedState } from "./NamedState";
import { TupleTerms } from "./TupleTerms";

/**
 * One horizon, headed by whether its rows are comparable at all and by where the benchmark
 * stands in **this** section.
 *
 * A failed section is a section: a survey that did not run, a comparison with no benchmark and a
 * dominance pass with nothing to run over each render their own member rather than an empty
 * column, because a column that fails to load and a column with nothing in it look the same.
 */
export function HorizonColumn({
  section,
  readings,
  shared,
}: {
  section: HorizonSection;
  readings: ReadonlyMap<string, KindReading>;
  shared: readonly string[];
}) {
  const survey = section.outcome.tag === "candidates.CandidateSurvey" ? section.outcome : null;
  const comparison =
    survey !== null && survey.comparison.tag === "tuple.Comparison" ? survey.comparison : null;
  const dominance =
    section.dominance.tag === "dominance.DominanceResult" ? section.dominance : null;
  const placed: readonly TupleOutcome[] = comparison === null ? [] : placeable(comparison);

  return (
    <section
      className="flex min-w-0 flex-col gap-3"
      data-horizon={section.horizon.end}
      aria-label={`${section.horizon.start} to ${section.horizon.end}`}
    >
      <h3 className="text-sm font-semibold">
        {day(section.horizon.start)} – {day(section.horizon.end)}
      </h3>

      {comparison !== null && spansDiffer(placed.map((held) => held.span)) ? (
        <ComparabilityBanner />
      ) : null}

      {survey === null ? <TypedState state={section.outcome} label="the survey did not run" /> : null}
      {survey !== null && comparison === null ? (
        <TypedState state={survey.comparison} label="there is no comparison" />
      ) : null}
      {dominance === null ? (
        <TypedState state={section.dominance} label="the dominance pass did not run" />
      ) : (
        <p className="text-xs" data-benchmark-standing={dominance.benchmark_standing.tag}>
          <BenchmarkStanding standing={dominance.benchmark_standing} />
        </p>
      )}

      {dominance !== null && comparison !== null ? (
        <>
          <p className="text-xs text-[var(--ink-muted)]" data-front-count={count(dominance.non_dominated.length)}>
            {count(dominance.non_dominated.length)} dominated by nothing
          </p>
          <ul className="space-y-3" data-front>
            {dominance.non_dominated.map((key) => {
              const joined = joinToOutcome(key, placed);
              return (
                <li key={listKey(key)}>
                  {joined.tag === "no-ranked-outcome" ? (
                    <TypedState
                      state={joined.key}
                      label="this key is on the front and in no ranked row"
                    />
                  ) : (
                    <CandidateCard
                      outcome={joined.outcome}
                      reading={
                        readings.get(joined.outcome.key.instrument_id) ?? { tag: "reading" }
                      }
                      shared={shared}
                      indistinguishable={indistinguishableFor(
                        joined.outcome,
                        dominance.indistinguishable,
                      )}
                    />
                  )}
                </li>
              );
            })}
          </ul>
        </>
      ) : null}

      {survey !== null && survey.comparison.tag === "tuple.BenchmarkUnavailable" ? (
        <>
          <Population
            name="scored, with no benchmark to compare against"
            members={survey.comparison.scored}
            render={(outcome) => <TupleTerms term={outcome.key} />}
          />
          <Population
            name="not comparable"
            members={survey.comparison.not_comparable}
            render={(outcome) => <TupleTerms term={outcome.key} />}
          />
          <Refusals refused={survey.comparison.refused} />
        </>
      ) : null}

      {comparison === null ? null : (
        <>
          <FullRanking comparison={comparison} />
          <Population
            name="beating the benchmark"
            members={comparison.beats_benchmark}
            render={(at) => <RankedRow comparison={comparison} at={at} />}
          />
          <Population
            name="not comparable"
            members={comparison.not_comparable}
            render={(outcome) => <TupleTerms term={outcome.key} />}
          />
          <Refusals refused={comparison.refused} />
        </>
      )}

      {survey === null ? null : (
        <div
          data-population="no candidate"
          data-count={count(survey.enumerated.no_candidate.length)}
        >
          <p className="text-xs text-[var(--ink-muted)]">
            pairs that yielded no candidate: {count(survey.enumerated.no_candidate.length)} of{" "}
            {count(survey.enumerated.pairs_considered)} considered
          </p>
          {groupNoCandidates(survey.enumerated.no_candidate).map((group) => (
            <RefusalGroup
              key={group.id}
              group={group}
              render={(member) => (
                <div data-no-candidate={member.instrument_id}>
                  <p className="font-mono">
                    {member.instrument_id} from {member.stream_id}
                  </p>
                  <p data-served-text="no-candidate">{member.why.reason}</p>
                </div>
              )}
            />
          ))}
        </div>
      )}

      {dominance === null ? null : (
        <>
          <Population
            name="not placed"
            members={dominance.not_placed}
            render={(held) => <TypedState state={held} label="not placed" />}
          />
          <Population
            name="incomparable pairs"
            members={dominance.incomparable}
            render={(held) => <TypedState state={held} label="incomparable" />}
          />
          <Population
            name="indistinguishable members"
            members={dominance.indistinguishable}
            render={(held) => (
              <div>
                <TupleTerms term={held.key} />
                <p>
                  within the band of{" "}
                  {held.neighbours.map((one) => one.instrument_id).join(", ")}
                </p>
              </div>
            )}
          />
          <Population
            name="dominated"
            members={dominance.dominated}
            render={(held) => <TupleTerms term={held.key} />}
          />
        </>
      )}

      <Population
        name="money arriving after the horizon"
        members={section.arrives_after_horizon}
        render={(held) => (
          <div>
            <TupleTerms term={held.key} />
            <p>arrives {day(held.arrives_on)}</p>
          </div>
        )}
      />
      <Population
        name="standings, by subject"
        members={section.standings}
        render={(held) => <TypedState state={held} label={held.named} />}
      />
      <Population
        name="reserves"
        members={section.reserves}
        render={(held) => <TypedState state={held} label="reserve" />}
      />
      <Population
        name="what this section does not account for"
        members={section.excludes}
        render={(held) => (
          <Disclosure name="exclusion" summary={held.what}>
            <p data-served-text="exclusion">
              supplied by {held.supplied_by}
              {held.direction === null ? "" : `, and it errs: ${held.direction}`}
            </p>
          </Disclosure>
        )}
      />
    </section>
  );
}

/** FR-022 and FR-023: the refused tuples of either comparison member, grouped by their tag. */
function Refusals({ refused }: { refused: readonly RefusedTuple[] }) {
  return (
    <div data-population="refused" data-count={count(refused.length)}>
      <p className="text-xs text-[var(--ink-muted)]">refused: {count(refused.length)}</p>
      {groupRefusals(refused).map((group) => (
        <RefusalGroup
          key={group.id}
          group={group}
          render={(member) => (
            <div>
              <TupleTerms term={member.key} />
              <p data-served-text="refusal">{member.refusal.reason}</p>
            </div>
          )}
        />
      ))}
    </div>
  );
}

function RankedRow({ comparison, at }: { comparison: Comparison; at: number }) {
  const outcome = comparison.ranked[at];
  if (outcome === undefined) {
    return <TypedState state={{ tag: "index-out-of-range", at }} label="the API sent an index" />;
  }
  return <TupleTerms term={outcome.key} />;
}

function BenchmarkStanding({ standing }: { standing: Standing }) {
  switch (standing.tag) {
    case "dominance.NothingDominatesTheHurdle":
      return (
        <span>
          nothing dominates the hurdle{" "}
          <span className="font-mono">{standing.key.instrument_id}</span> in this section
        </span>
      );
    case "dominance.HurdleIsDominated":
      return (
        <span>
          the hurdle <span className="font-mono">{standing.key.instrument_id}</span> is dominated
          here, by {count(standing.by.length)}
        </span>
      );
  }
  assertNever(standing);
}
