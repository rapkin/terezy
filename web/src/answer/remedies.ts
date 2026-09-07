/**
 * FR-021: a subject the registry declares nothing by renders as a refusal carrying its remedy.
 *
 * The remedy belongs on the record (OB-17) — `answer.UndeclaredSubject` carries only the word
 * the owner wrote — so until it does, the map from that word to the feature that supplies the
 * declaration lives here, in one place, and a subject with no entry renders the half it knows
 * rather than a blank.
 */
export type Remedy = {
  readonly remedy: string;
  readonly suppliedBy: string | null;
};

const DECLARATION = "a declaration";

const SUPPLIED_BY: Readonly<Record<string, string>> = {};
/* Empty since 2026-09-07, when 025 declared the last undeclared subject the shipped answer
   reported. The map stays because the next subject the owner names before he declares it goes
   here rather than rendering with no feature behind its remedy. */

export function remedyFor(named: string): Remedy {
  return { remedy: DECLARATION, suppliedBy: SUPPLIED_BY[named] ?? null };
}
