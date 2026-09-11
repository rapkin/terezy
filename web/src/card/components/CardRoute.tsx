/**
 * FR-028: the card, opened from **any** ranked row and closable back to the reader's place.
 *
 * Any row and not only a non-dominated one: the reader who most needs the reason for a figure is
 * the one who was not shown it. Closing is a link back to the answer carrying the same `as_of`,
 * beside the browser's own back — the row is a `Link`, so a card opened from the screen is one
 * history entry and the reader lands where he left.
 *
 * SC-006: opening one issues **one** request. The answer is already in the cache when the reader
 * came from the screen, and the projection is the one read this route adds.
 */
import { Link, createRoute } from "@tanstack/react-router";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import type { Answered } from "@/api/client";
import { answerQuery, projectionQuery } from "@/api/queries";
import { outcomeFor } from "@/card/lookup";
import { remedyFor } from "@/card/refusals";
import { isTheAnswer, isTheCandidateProjection } from "@/lib/narrow";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { TypedState } from "@/answer/components/NamedState";
import { rootRoute } from "@/routes/root";
import { Awaiting, useAsOf } from "@/routes/read";
import { CandidateCard } from "./CandidateCard";

export const cardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/questions/$questionId/candidates/$candidateKey",
  component: CardScreen,
});

function CardScreen() {
  const { questionId, candidateKey } = cardRoute.useParams();
  const asOf = useAsOf();
  const enabled = asOf !== undefined;
  const served = useQuery({
    ...projectionQuery(questionId, candidateKey, asOf ?? ""),
    enabled,
  });
  // Never stale for this observer: the answer is keyed by `as_of`, so the cached one is the
  // answer this key belongs to however long the reader took to click. The shared 30-second
  // staleness would refetch 8.5 MB and make SC-006's *one request* a claim about how fast he is.
  const answered = useQuery({
    ...answerQuery(questionId, asOf ?? ""),
    enabled,
    staleTime: Number.POSITIVE_INFINITY,
  });

  if (!enabled) return null;
  return (
    <div className="space-y-4">
      <Close asOf={asOf} />
      <Body
        served={served.data}
        answered={answered.data}
        candidateKey={candidateKey}
        waiting={{ flows: served, answer: answered }}
      />
    </div>
  );
}

function Close({ asOf }: { asOf: string }) {
  return (
    <Link to="/" search={{ as_of: asOf }} className="text-xs underline" data-close-card>
      ← back to the answer
    </Link>
  );
}

function Body({
  served,
  answered,
  candidateKey,
  waiting,
}: {
  served: Answered | undefined;
  answered: Answered | undefined;
  candidateKey: string;
  waiting: {
    readonly flows: UseQueryResult<Answered>;
    readonly answer: UseQueryResult<Answered>;
  };
}) {
  if (served === undefined) return <Awaiting what="this candidate's flows" query={waiting.flows} />;
  if (served.tag !== "body" || !isTheCandidateProjection(served.body)) {
    return <ApiErrorState answered={served} what="this candidate's flows" />;
  }
  const result = served.body.result;
  // Before the answer, deliberately: a refused key reads nothing from it, and the one reader who
  // is certainly not going to see a card should not wait out an 8.5 MB fetch to be told so.
  if (result.tag !== "projection.ProjectedCandidate") {
    return (
      <TypedState
        state={{ ...result, remedy: remedyFor(result) }}
        label="this candidate has no card"
      />
    );
  }
  if (answered === undefined) {
    return <Awaiting what="the answer this candidate belongs to" query={waiting.answer} />;
  }
  if (answered.tag !== "body" || !isTheAnswer(answered.body)) {
    return <ApiErrorState answered={answered} what="the answer this candidate belongs to" />;
  }
  const answer = answered.body.result;
  if (answer.tag !== "answer.AnsweredQuestion" || answer.answer.tag !== "answer.Answer") {
    return <TypedState state={answer} label="the question was not answered" />;
  }
  const located = outcomeFor(candidateKey, answer.answer);
  if (located.tag === "not-in-this-answer") {
    // The endpoint resolved the key and this answer does not carry it, which can only mean the
    // two were read at different dates. A named state rather than a card with empty slots.
    return (
      <TypedState
        state={{
          tag: "answer-and-card-disagree",
          key: located.key,
          remedy: "reopen the answer: this card and the answer beside it were read as of different dates",
        }}
        label="this candidate is not in the answer beside it"
      />
    );
  }
  return <CandidateCard projection={result.projection} outcome={located.outcome} />;
}
