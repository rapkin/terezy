import type { Checked, OutsideCoverage } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";
import { Refusal } from "@/components/figure/Refusal";

/**
 * FR-029: the refusal for the part of the window the series does not cover, rendered **beside**
 * the observations that were covered and never in place of them.
 *
 * The `checked` statement is rendered with it because *no refusal* and *nothing was checked* are
 * different facts, and only the API knows which of the two a given read produced.
 */
export function CoverageRefusal({
  outside,
  checked,
}: {
  outside: OutsideCoverage | null;
  checked: Checked;
}) {
  return (
    <div className="space-y-2">
      {outside !== null && <Refusal refusal={outside} />}
      <CheckedNote checked={checked} />
    </div>
  );
}

function CheckedNote({ checked }: { checked: Checked }) {
  switch (checked.tag) {
    case "envelopes.NoWindowAsked":
      return (
        <p data-checked="none" className="text-xs text-[var(--ink-muted)]">
          no window was asked for, so the whole declared coverage was returned and nothing was
          checked against one.
        </p>
      );
    case "envelopes.EveryPeriodChecked":
      return (
        <p data-checked="every" className="text-xs text-[var(--ink-muted)]">
          every period of the asked window was checked against the declaration.
        </p>
      );
    case "envelopes.OnlyTheEndsChecked":
      return (
        <p data-checked="ends" className="text-xs text-[var(--warn-ink)]">
          {checked.reason}
        </p>
      );
  }
  assertNever(checked);
}
