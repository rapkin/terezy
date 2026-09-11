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
import { useQuery } from "@tanstack/react-query";
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
  const answered = useQuery({ ...answerQuery(questionId, asOf ?? ""), enabled });

  if (!enabled) return null;
  return (
    <div className="space-y-4">
      <Close asOf={asOf} />
      <Body served={served.data} answered={answered.data} candidateKey={candidateKey} />
      {served.data === undefined ? <Awaiting what="this candidate's flows" query={served} /> : null}
      {served.data !== undefined && answered.data === undefined ? (
        <Awaiting what="the answer this candidate belongs to" query={answered} />
      ) : null}
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
}: {
  served: Answered | undefined;
  answered: Answered | undefined;
  candidateKey: string;
}) {
  if (served === undefined || answered === undefined) return null;
  if (served.tag !== "body" || !isTheCandidateProjection(served.body)) {
    return <ApiErrorState answered={served} what="this candidate's flows" />;
  }
  const result = served.body.result;
  if (result.tag !== "projection.ProjectedCandidate") {
    return (
      <TypedState
        state={{ ...result, remedy: remedyFor(result) }}
        label="this candidate has no card"
      />
    );
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
