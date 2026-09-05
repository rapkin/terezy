/** FR-038: every route offers a skip link to its main content. */
export function SkipLink() {
  return (
    <a
      href="#main"
      className="sr-only rounded bg-[var(--surface-raised)] px-2 py-1 underline focus:not-sr-only focus:absolute focus:top-2 focus:left-2"
    >
      Skip to main content
    </a>
  );
}
