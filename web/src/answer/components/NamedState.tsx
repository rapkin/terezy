import type { FieldNotServed } from "@/answer/missing";
import { count, plain } from "@/design/format";
import { isRecord } from "@/lib/narrow";
import { LongValue } from "@/components/record/LongValue";

/**
 * FR-010: a field the response does not carry says **which** field and what would supply it.
 *
 * Never a blank, a zero, a dash or an empty slot.
 */
export function FieldMissing({ state }: { state: FieldNotServed }) {
  return (
    <p
      role="note"
      data-figure="refused"
      data-missing={state.field}
      className="rounded border border-[var(--warn-border)] bg-[var(--warn-surface)] p-2 text-xs text-[var(--warn-ink)]"
    >
      the API sent no <strong>{state.field}</strong> — {state.obligation}
    </p>
  );
}

/**
 * A member of a served union that is a state rather than a result: a survey that did not run, a
 * comparison with no benchmark, a dominance pass that had nothing to run over.
 *
 * Its fields are walked rather than switched over. The three unions this renders have
 * twenty-seven members between them, every one of which carries its own reason or its own typed
 * fields and nothing else — a switch would be twenty-seven arms restating field names, and a
 * member added to any of them would render **blank** until somebody wrote the twenty-eighth.
 * Walking cannot leave a member unrendered.
 */
export function TypedState({ state, label }: { state: object; label: string }) {
  const fields = isRecord(state) ? Object.keys(state) : [];
  const reason = isRecord(state) && typeof state["reason"] === "string" ? state["reason"] : null;
  return (
    <div
      role="note"
      data-typed-state={tagText(state)}
      className="space-y-1 rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-2 text-[var(--refuse-ink)]"
    >
      <p className="text-xs font-semibold">
        {label}: {tagText(state)}
      </p>
      {reason === null ? null : (
        <div data-served-text="reason">
          <LongValue text={reason} />
        </div>
      )}
      <ul className="ml-4 list-disc text-xs">
        {fields
          .filter((field) => field !== "tag" && field !== "reason")
          .map((field) => (
            <li key={field} data-state-field={field}>
              {field}: {described(isRecord(state) ? state[field] : undefined)}
            </li>
          ))}
      </ul>
    </div>
  );
}

function tagText(state: object): string {
  return isRecord(state) && typeof state["tag"] === "string" ? state["tag"] : "an untagged member";
}

/** One field of a typed state, in words. Numbers go through the formatter like every figure. */
function described(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number") return plain(value);
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (value === null) return "not stated";
  if (Array.isArray(value)) return `${count(value.length)} of them`;
  if (isRecord(value)) return typeof value["tag"] === "string" ? value["tag"] : "a record";
  return "not stated";
}
