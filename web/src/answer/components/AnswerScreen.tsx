import type { AnsweredQuestion, HorizonSection, TupleOutcome } from "@/api/shapes";
import { sharedAcross } from "@/answer/assumptions";
import { joinToOutcome } from "@/answer/join";
import { beliefsAcross, sentencesNaming, withoutBeliefs } from "@/answer/beliefs";
import type { KindReading } from "@/answer/instrument-kind";
import { AnswerHeader } from "./AnswerHeader";
import { HorizonColumn } from "./HorizonColumn";
import { TypedState } from "./NamedState";
import { SharedAssumptions } from "./SharedAssumptions";

/**
 * The answer, drawn: the question in words, what every candidate rests on, then the horizons
 * side by side.
 *
 * Side by side rather than behind a tab strip (owner, 2026-09-06): the cross-horizon reading is
 * what a three-horizon question *is*, and a tab strip makes it a memory exercise.
 */
export function AnswerScreen({
  answered,
  readings,
}: {
  answered: AnsweredQuestion;
  readings: ReadonlyMap<string, KindReading>;
}) {
  const answer = answered.answer;
  if (answer.tag !== "answer.Answer") {
    return <TypedState state={answer} label="the question was not answered" />;
  }
  const shown = membersShown(answer.sections);
  const beliefs = beliefsAcross(shown);
  const shared = withoutBeliefs(
    sharedAcross(shown.map((outcome) => outcome.rests_on)),
    beliefs,
  );
  return (
    <div className="space-y-4" data-answer>
      <AnswerHeader answer={answer} />
      <SharedAssumptions
        shared={shared}
        beliefs={beliefs}
        statedAs={(belief) => sentencesNaming(belief, shown)}
      />
      <div className="grid gap-4 lg:grid-cols-3" data-columns>
        {answer.sections.map((section) => (
          <HorizonColumn
            key={section.horizon.end}
            section={section}
            readings={readings}
            shared={shared}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * Every member shown on a card, across every section.
 *
 * FR-020's *shared* is over these and not over `ranked`: an assumption every **shown** member
 * rests on is what goes once at the top, and folding one that only the dominated rows carry
 * would state it above cards that do not rest on it.
 */
export function membersShown(sections: readonly HorizonSection[]): readonly TupleOutcome[] {
  const shown: TupleOutcome[] = [];
  for (const section of sections) {
    if (section.outcome.tag !== "candidates.CandidateSurvey") continue;
    const comparison = section.outcome.comparison;
    if (comparison.tag !== "tuple.Comparison") continue;
    if (section.dominance.tag !== "dominance.DominanceResult") continue;
    for (const key of section.dominance.non_dominated) {
      const joined = joinToOutcome(key, comparison.ranked);
      if (joined.tag === "joined") shown.push(joined.outcome);
    }
  }
  return shown;
}

/**
 * The instrument ids the tiles need a read for — **distinct**, so a member on two fronts is one
 * request rather than two (plan Finding 1 counts ten across the three fronts).
 */
export function memberIds(sections: readonly HorizonSection[]): readonly string[] {
  return [...new Set(membersShown(sections).map((held) => held.key.instrument_id))];
}
