import type { Tuple } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";

/**
 * Principle VI: an option is five terms, and a row headed by an instrument id alone is four of
 * them missing. `cli/main.py::_candidate` answers the same complaint at the terminal.
 */
export function TupleTerms({ term }: { term: Tuple }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-2 text-xs" data-terms>
      <Term name="instrument" value={term.instrument_id} />
      <Term name="funded from" value={term.stream_id} />
      <Term name="route in" value={wayIn(term.route_in)} />
      <Term name="exit terms" value={exitTerms(term.exit_terms)} />
      <Term name="route out" value={wayOut(term.route_out)} />
    </dl>
  );
}

function Term({ name, value }: { name: string; value: string }) {
  return (
    <>
      <dt className="text-[var(--ink-muted)]">{name}</dt>
      <dd data-term={name} className="font-mono">
        {value}
      </dd>
    </>
  );
}

function wayIn(path: Tuple["route_in"]): string {
  switch (path.tag) {
    case "path.FundingPath":
      return `${path.route_id} → ${path.destination_id}`;
    case "path.ComposedPath":
      return `${path.segments.join(" → ")} → ${path.destination_id}`;
  }
  assertNever(path);
}

function wayOut(path: Tuple["route_out"]): string {
  if (path === "exit_by_identity") return "exit by identity";
  if (path === "from_the_declaration") return "from the declaration";
  switch (path.tag) {
    case "path.DeclaredExit":
      return path.route_id;
    case "path.ComposedExit":
      return path.segments.join(" → ");
  }
  assertNever(path);
}

function exitTerms(terms: Tuple["exit_terms"]): string {
  switch (terms.tag) {
    case "interface.Assumptions":
      return `${terms.consumption_method}, coupons ${terms.coupon_policy}`;
    case "fund.FundAssumptions":
      // `exit_on` is null where the fund states no exit date, and a template would print it as
      // the word "null" — which reads as a date nobody declared.
      return [
        terms.consumption_method,
        `${terms.liquidity_mode} liquidity`,
        `buyback ${terms.buyback}`,
        terms.exit_on === null ? "no exit date declared" : `exit ${terms.exit_on}`,
      ].join(", ");
  }
  assertNever(terms);
}
