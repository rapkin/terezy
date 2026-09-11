/**
 * FR-028: the link that opens a candidate's card, on **any** ranked row.
 *
 * The key is the one the answer published on the outcome, echoed verbatim. This client never
 * composes one: a key it built from the five terms would name three candidates — the same
 * candidate is evaluated once per section — and would address the wrong projection two times
 * in three.
 */
import { Link, useSearch } from "@tanstack/react-router";
import type { TupleOutcome } from "@/api/shapes";

export function WhyLink({
  outcome,
  questionId,
}: {
  outcome: TupleOutcome;
  questionId: string;
}) {
  const search: { as_of?: string } = useSearch({ strict: false });
  return (
    <Link
      to="/questions/$questionId/candidates/$candidateKey"
      params={{ questionId, candidateKey: outcome.projection_key }}
      search={{ as_of: search.as_of }}
      className="text-xs underline"
      data-open-card={outcome.projection_key}
    >
      why exactly this figure
    </Link>
  );
}
