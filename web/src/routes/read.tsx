import type { UseQueryResult } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import type { Answered } from "@/api/client";
import { parseAsOf, parseWindow, stringOrUndefined, type Parsed, type Window } from "@/search/params";
import { ApiErrorState } from "@/components/shell/ApiErrorState";

/** The validated `as_of` of whatever route asked, or nothing where the URL does not carry one. */
export function useAsOf(): string | undefined {
  const search: Record<string, unknown> = useSearch({ strict: false });
  const parsed = parseAsOf(stringOrUndefined(search["as_of"]));
  return parsed.tag === "given" ? parsed.value : undefined;
}

/** The window a series route was asked for, in the three states FR-027 gives it. */
export function useWindow(): Parsed<Window> {
  const search: Record<string, unknown> = useSearch({ strict: false });
  return parseWindow(stringOrUndefined(search["from"]), stringOrUndefined(search["to"]));
}

/**
 * FR-006: a query that has not resolved is a stated wait, and one that failed is a named state.
 *
 * Never an empty list and never a spinner that never resolves -- the failure branch is what
 * stops the second, because a rejected query would otherwise leave `data` undefined for ever.
 */
export function Awaiting({ what, query }: { what: string; query: UseQueryResult<Answered> }) {
  if (query.isError) {
    return (
      <ApiErrorState
        answered={{
          tag: "unreachable",
          detail: query.error instanceof Error ? query.error.message : String(query.error),
        }}
        what={what}
      />
    );
  }
  return (
    <p role="status" data-awaiting={what}>
      reading {what}…
    </p>
  );
}
