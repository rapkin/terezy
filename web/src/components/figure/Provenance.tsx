import type { Provenance as ProvenanceValue, StalenessVerdict } from "@/api/shapes";
import { marksOf } from "@/lib/provenance";
import { Mark } from "./Mark";
import { LongValue } from "@/components/record/LongValue";

/**
 * FR-017: the citation, `retrieved_on` and `verified_on` of every source behind a value.
 *
 * An empty `verified_on` renders as the unverified mark and never as an empty field, and the
 * stale mark is a separate claim carried only where the response's verdict names the source
 * (FR-012).
 */
export function Provenance({
  provenance,
  verdict,
}: {
  provenance: ProvenanceValue;
  verdict?: StalenessVerdict | undefined;
}) {
  const marks = marksOf(provenance, verdict);
  const marksBySource = new Map<string, typeof marks>();
  for (const mark of marks) {
    marksBySource.set(mark.source.id, [...(marksBySource.get(mark.source.id) ?? []), mark]);
  }
  return (
    <ul data-provenance={provenance.is_unverified ? "unverified" : "verified"} className="mt-1 space-y-2">
      {provenance.sources.map((source) => (
        <li key={source.id} className="border-l-2 border-[var(--border)] pl-2 text-xs">
          <p className="font-mono">{source.id}</p>
          <span data-citation={source.id}>
            <LongValue text={source.citation} />
          </span>
          <p>
            kind {source.kind} · retrieved_on {source.retrieved_on} · verified_on{" "}
            {source.verified_on ?? "not recorded"}
          </p>
          <span className="mt-1 inline-flex flex-wrap gap-1">
            {(marksBySource.get(source.id) ?? []).map((mark) => (
              <Mark key={mark.tag} mark={mark} />
            ))}
          </span>
        </li>
      ))}
    </ul>
  );
}
