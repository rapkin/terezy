import { useEffect, useState } from "react";

/**
 * FR-021, FR-022: `as_of` is shown and edited, and editing it changes the URL.
 *
 * It reads no clock -- the only read is the router's redirect on a first load without one -- and
 * changing it re-queries rather than re-ageing anything already on screen.
 */
export function AsOfControl({
  asOf,
  onChange,
}: {
  asOf: string;
  onChange: (next: string) => void;
}) {
  const [draft, setDraft] = useState(asOf);
  // Resynced because this control outlives the route: a Back button changes the URL under it,
  // and a draft that kept the older value would re-apply a date the reader did not ask for.
  useEffect(() => {
    setDraft(asOf);
  }, [asOf]);
  return (
    <form
      className="flex items-center gap-2 text-xs"
      onSubmit={(event) => {
        event.preventDefault();
        onChange(draft);
      }}
    >
      <label htmlFor="as-of">as_of</label>
      <input
        id="as-of"
        name="as_of"
        value={draft}
        onChange={(event) => {
          setDraft(event.target.value);
        }}
        className="rounded border border-[var(--border)] bg-[var(--surface-raised)] px-1 py-0.5 font-mono"
      />
      <button
        type="submit"
        className="rounded border border-[var(--border)] px-2 py-0.5 hover:bg-[var(--surface)]"
      >
        read as of this date
      </button>
      <span data-as-of={asOf} className="text-[var(--ink-muted)]">
        reading as of {asOf}
      </span>
    </form>
  );
}
