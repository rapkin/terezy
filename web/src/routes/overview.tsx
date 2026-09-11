import type { Answered } from "@/api/client";
import { createRoute } from "@tanstack/react-router";
import { useQueries, useQuery } from "@tanstack/react-query";
import { answerQuery, declaredQuestionsQuery, instrumentQuery } from "@/api/queries";
import { isListing, isTheAnswer } from "@/lib/narrow";
import { kindOf, type KindReading } from "@/answer/instrument-kind";
import { memberIds } from "@/answer/components/AnswerScreen";
import { AnswerScreen } from "@/answer/components/AnswerScreen";
import { AnswerQueryFailed, AnswerUnavailable, LoadingState } from "@/answer/components/States";
import { TypedState } from "@/answer/components/NamedState";
import { rootRoute } from "./root";
import { useAsOf } from "./read";

/**
 * FR-028: `/` is the answer.
 *
 * A change of meaning rather than an omission — 021's category index lived here and now lives at
 * `/data` — and there is deliberately **no redirect**: one from `/` would send every visitor to
 * the browser and defeat the feature. A bookmarked `/` reaches the answer.
 */
export const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: TheAnswer,
});

function TheAnswer() {
  const asOf = useAsOf();
  const enabled = asOf !== undefined;
  // The question's id is read off the declared ids rather than written here: an id in the client
  // is a declaration in two places, and the one in `data/` is the one that is reviewed.
  const declared = useQuery({ ...declaredQuestionsQuery(asOf ?? ""), enabled });
  const questionId = firstDeclared(declared.data);
  const answered = useQuery({
    ...answerQuery(questionId ?? "", asOf ?? ""),
    enabled: enabled && questionId !== undefined,
  });
  const answer = isTheAnswer(bodyOf(answered.data)) ? bodyOf(answered.data) : undefined;
  const ids = answer === undefined ? [] : idsIn(answer);
  const reads = useQueries({
    queries: ids.map((id) => ({ ...instrumentQuery(id, asOf ?? ""), enabled })),
  });

  if (!enabled) return null;
  if (declared.isError) return <AnswerQueryFailed query={declared} />;
  if (declared.data === undefined) return <LoadingState />;
  // Read before the id: `request` answers an unreachable API with a typed value rather than by
  // rejecting, so a route that went straight to the id would report a service that is down as a
  // registry that declares no question.
  if (declared.data.tag !== "body" || !isListing(declared.data.body)) {
    return <AnswerUnavailable answered={declared.data} />;
  }
  if (questionId === undefined) {
    return (
      <p role="note" data-nothing-declared className="text-sm">
        nothing under <code>data/questions</code> declares a question, so there is nothing to
        answer. A question is a declaration: it is changed in git and reviewed like code.
      </p>
    );
  }
  if (answered.isError) return <AnswerQueryFailed query={answered} />;
  if (answered.data === undefined) return <LoadingState />;
  if (answered.data.tag !== "body" || !isTheAnswer(answered.data.body)) {
    return <AnswerUnavailable answered={answered.data} />;
  }
  const result = answered.data.body.result;
  if (result.tag !== "answer.AnsweredQuestion") {
    return <TypedState state={result} label="the question was not answered" />;
  }
  const readings = new Map<string, KindReading>(
    ids.map((id, at) => [id, readingOf(reads[at])]),
  );
  return <AnswerScreen answered={result} readings={readings} questionId={questionId} />;
}

function bodyOf(answered: Answered | undefined): unknown {
  return answered?.tag === "body" ? answered.body : undefined;
}

function firstDeclared(answered: Answered | undefined): string | undefined {
  const body = bodyOf(answered);
  return isListing(body) ? body.ids[0] : undefined;
}

function idsIn(body: unknown): readonly string[] {
  if (!isTheAnswer(body)) return [];
  const result = body.result;
  if (result.tag !== "answer.AnsweredQuestion") return [];
  return result.answer.tag === "answer.Answer" ? memberIds(result.answer.sections) : [];
}

function readingOf(read: { readonly data: Answered | undefined } | undefined): KindReading {
  if (read?.data === undefined) return { tag: "reading" };
  return kindOf(bodyOf(read.data));
}
