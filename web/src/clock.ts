/**
 * FR-021, FR-021a: the client's only read of a clock, guarded by the ESLint rule that fails any
 * `new Date()` or `Date.now()` elsewhere under `src/`.
 *
 * A second read is how the `as_of` in the URL and the date a figure was aged at come to
 * disagree, which is the defect the redirect exists to prevent.
 */
export function today(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, "0");
  const day = String(now.getDate()).padStart(2, "0");
  return `${String(now.getFullYear())}-${month}-${day}`;
}
