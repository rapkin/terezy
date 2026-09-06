import type { ReactNode } from "react";

/**
 * FR-025: long provenance text is behind a disclosure and reachable in full.
 *
 * `<details>` rather than a toggle of our own: it is keyboard-operable and announced without
 * anything being wired up, which is FR-027's requirement rather than a convenience.
 */
export function Disclosure({
  summary,
  count,
  name,
  children,
}: {
  summary: ReactNode;
  count?: number;
  name?: string;
  children: ReactNode;
}) {
  return (
    <details className="rounded border border-[var(--border)] px-2 py-1" data-disclosure={name}>
      <summary className="cursor-pointer text-xs">
        {summary}
        {count === undefined ? null : <span className="ml-1 text-[var(--ink-muted)]">({count})</span>}
      </summary>
      <div className="mt-2 space-y-2 text-xs">{children}</div>
    </details>
  );
}
