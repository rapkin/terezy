import type { Refusal as RefusalValue } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";
import { LongValue } from "@/components/record/LongValue";

/**
 * FR-007's refusal state, and FR-008's prohibition: never a blank, `0`, `—`, `n/a` or an empty
 * series in this position.
 *
 * The switch narrows on the **tag** before the reason, because the member's own fields are what
 * says which thing could not be produced, and a reason alone would leave that unsaid.
 */
export function Refusal({ refusal }: { refusal: RefusalValue }) {
  return (
    <div
      role="note"
      data-figure="refused"
      data-refusal={refusal.tag}
      className="rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-2 text-[var(--refuse-ink)]"
    >
      <p className="text-xs font-semibold">refused: {refusal.tag}</p>
      <LongValue text={refusal.reason} />
      <RefusalDetail refusal={refusal} />
    </div>
  );
}

function RefusalDetail({ refusal }: { refusal: RefusalValue }) {
  switch (refusal.tag) {
    case "envelopes.CategoryHasNoSuchId":
      return (
        <Detail>
          the category {refusal.category} declares {refusal.declared_ids.join(", ")}, and none of
          them is {refusal.wanted_id}
        </Detail>
      );
    case "envelopes.ScenarioNotDeclared":
      return (
        <Detail>
          no scenario {refusal.wanted_id} is declared; the declared ones are{" "}
          {refusal.declared_ids.join(", ")}
        </Detail>
      );
    case "envelopes.NothingDeclared":
      return <Detail>nothing under {refusal.category} declares a document</Detail>;
    case "envelopes.FileNotRecorded":
      return <Detail>the declaring file of a {refusal.category} record was not recorded</Detail>;
    case "envelopes.WindowMalformed":
      return (
        <Detail>
          the window asked of {refusal.series_id} was {refusal.asked.join(" .. ")}
        </Detail>
      );
    case "envelopes.WindowOutsideCoverage":
      return (
        <Detail>
          {refusal.series_id} covers{" "}
          {refusal.covers === null ? "nothing it declares" : refusal.covers.join(" .. ")}; the
          window asked for {refusal.asked.join(" .. ")} and the uncovered part is{" "}
          {refusal.missing.join(", ")}
        </Detail>
      );
    case "middleware.HostNotDeclared":
      return (
        <Detail>
          the request named the host {refusal.host ?? "none"}; the declared hosts are{" "}
          {refusal.declared.join(", ")}
        </Detail>
      );
    case "middleware.NotOnLoopback":
      return <Detail>the client address was {refusal.client_address ?? "not recorded"}</Detail>;
    case "service.PathNotServed":
      return <Detail>no route serves {refusal.path}</Detail>;
  }
  assertNever(refusal);
}

function Detail({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-xs">{children}</p>;
}
