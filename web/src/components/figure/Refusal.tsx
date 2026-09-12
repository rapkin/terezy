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
    <RefusalChrome tag={refusal.tag} reason={refusal.reason}>
      <RefusalDetail refusal={refusal} />
    </RefusalChrome>
  );
}

/**
 * The refusal's rendering, apart from the union it narrows.
 *
 * The answer carries refusals of its own — `tuple.RateNotComparable`, and sixteen more inside a
 * `RefusedTuple` — which are **not** members of the envelope union above and cannot be: that
 * union is what the switch here is exhaustive over, and widening it would replace a total
 * renderer with forty arms. They reach the same chrome through this, so a refused figure looks
 * like every other refused figure rather than like a second thing.
 */
export function RefusalChrome({
  tag,
  reason,
  children,
}: {
  tag: string;
  reason: string;
  children?: React.ReactNode;
}) {
  return (
    <div
      role="note"
      data-figure="refused"
      data-refusal={tag}
      className="rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-2 text-[var(--refuse-ink)]"
    >
      <p className="text-xs font-semibold">refused: {tag}</p>
      <div data-served-text="reason">
        <LongValue text={reason} />
      </div>
      {children}
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
    case "envelopes.RequestMalformed":
      return (
        <ul className="mt-1 ml-4 list-disc text-xs">
          {/* The index is in the key because one parameter can fail several ways at once: the
              validator reports one fault per union member it tried, so the location repeats. */}
          {refusal.parameters.map((parameter, at) => (
            <li key={`${String(at)}:${parameter.location.join(".")}`} data-parameter={parameter.location.join(".")}>
              {parameter.location.join(" → ")} was{" "}
              {parameter.given === null ? "not given" : `given as ${parameter.given}`}:{" "}
              {parameter.problem}
            </li>
          ))}
        </ul>
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
    case "middleware.BodyLengthNotDeclared":
      return (
        <Detail>
          a {refusal.method} request must declare its body length; the cap is {refusal.limit_bytes}{" "}
          bytes
        </Detail>
      );
    case "middleware.BodyTooLarge":
      return (
        <Detail>
          the body declares {refusal.declared_bytes} bytes against a cap of {refusal.limit_bytes}
        </Detail>
      );
    case "service.PathNotServed":
      return <Detail>no route serves {refusal.path}</Detail>;
    case "card.NoSuchCandidate":
      return (
        <Detail>
          no candidate of this answer is addressed by {refusal.wanted_key}; it published{" "}
          {refusal.evaluated_keys.length} key(s)
        </Detail>
      );
  }
  assertNever(refusal);
}

function Detail({ children }: { children: React.ReactNode }) {
  return <p className="mt-1 text-xs">{children}</p>;
}
