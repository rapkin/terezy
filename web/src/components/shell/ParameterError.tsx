import type { Parsed } from "@/search/params";

/**
 * FR-020: an invalid search parameter is a visible error naming the parameter, and nothing is
 * substituted for it. A default put in quietly is the silent clamp Principle IV forbids,
 * arriving through the URL.
 */
export function ParameterError({ parsed }: { parsed: Extract<Parsed<never>, { tag: "invalid" }> }) {
  return (
    <div
      role="alert"
      data-parameter-error={parsed.parameter}
      className="rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-3 text-[var(--refuse-ink)]"
    >
      <p className="font-semibold">the parameter {parsed.parameter} is not valid</p>
      <p className="text-sm">
        given {JSON.stringify(parsed.given)} — {parsed.reason}
      </p>
    </div>
  );
}
