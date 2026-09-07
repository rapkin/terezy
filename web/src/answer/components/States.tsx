import type { UseQueryResult } from "@tanstack/react-query";
import type { Answered } from "@/api/client";
import { ApiErrorState } from "@/components/shell/ApiErrorState";

/**
 * FR-013: the wait is named, and the failure is named.
 *
 * The answer is megabytes on the wire (OB-10), so the wait is one a reader must be able to tell
 * from a hang — which is why the state says what is being read and how big it is rather than
 * spinning.
 */
export function LoadingState() {
  return (
    <p role="status" data-awaiting="the answer" className="text-sm">
      reading the answer to the declared question. It is megabytes on the wire — every verdict
      carries both candidates&apos; provenance — so this takes a moment.
    </p>
  );
}

export function AnswerUnavailable({ answered }: { answered: Answered }) {
  return <ApiErrorState answered={answered} what="the answer" />;
}

/** The failure branch of a query that rejected, in the same named state (021's `Awaiting`). */
export function AnswerQueryFailed({ query }: { query: UseQueryResult<Answered> }) {
  return (
    <AnswerUnavailable
      answered={{
        tag: "unreachable",
        detail: query.error instanceof Error ? query.error.message : String(query.error),
      }}
    />
  );
}
