import type { ReactNode } from "react";
import { SkipLink } from "./SkipLink";
import { ThemeToggle } from "./ThemeToggle";

/**
 * FR-038: keyboard reach, a visible focus indicator, no focus trap, and a skip link on every
 * route. The focus outline is defined once in `styles.css` for `:focus-visible`.
 */
export function AppShell({
  nav,
  control,
  children,
}: {
  nav: ReactNode;
  control?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="mx-auto max-w-5xl p-4">
      <SkipLink />
      <header className="mb-4 space-y-2 border-b border-[var(--border)] pb-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h1 className="text-lg font-semibold">terezy — the declared data</h1>
          <ThemeToggle />
        </div>
        <nav aria-label="sections" className="flex flex-wrap gap-3 text-sm">
          {nav}
        </nav>
        {control}
      </header>
      <main id="main" tabIndex={-1}>
        {children}
      </main>
    </div>
  );
}
