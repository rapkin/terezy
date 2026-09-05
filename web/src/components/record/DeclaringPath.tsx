import type { RecordRead } from "@/api/shapes";
import { isRefusal } from "@/lib/provenance";
import { Refusal } from "@/components/figure/Refusal";

/** FR-018: the path of the file that declares this record, as text under its heading. */
export function DeclaringPath({ declaredIn }: { declaredIn: RecordRead["declared_in"] }) {
  if (declaredIn === null) {
    return (
      <p data-declared-in="none" className="font-mono text-xs text-[var(--ink-muted)]">
        declared in: no file recorded for this record
      </p>
    );
  }
  if (isRefusal(declaredIn)) return <Refusal refusal={declaredIn} />;
  return (
    <p data-declared-in={declaredIn} className="font-mono text-xs text-[var(--ink-muted)]">
      declared in: {declaredIn}
    </p>
  );
}
