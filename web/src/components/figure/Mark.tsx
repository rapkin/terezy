import type { Mark as MarkValue } from "@/lib/provenance";
import { assertNever } from "@/lib/exhaustive";
import { Badge } from "@/components/ui/badge";

/** FR-009: the mark is carried in **text**. Styling adds emphasis and never carries the claim. */
export function Mark({ mark }: { mark: MarkValue }) {
  switch (mark.tag) {
    case "unverified":
      return (
        <Badge tone="warn" data-mark="unverified">
          unverified — {mark.source.id} has no verified_on, retrieved {mark.source.retrieved_on}
        </Badge>
      );
    case "stale":
      return (
        <Badge tone="warn" data-mark="stale">
          stale — {mark.stale.source_id} was retrieved {mark.stale.retrieved_on}, {mark.stale.age_days} days
          old against a {mark.stale.threshold_days}-day threshold for {mark.stale.kind_id}, {mark.stale.overdue_days} days
          overdue
        </Badge>
      );
  }
  assertNever(mark);
}

export function Marks({ marks }: { marks: readonly MarkValue[] }) {
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1">
      {marks.map((mark) => (
        <Mark key={`${mark.tag}:${mark.source.id}`} mark={mark} />
      ))}
    </span>
  );
}
