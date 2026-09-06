import type { SeparatingBadge as Badgeable } from "@/answer/separating";
import { day } from "@/design/format";
import { assertNever } from "@/lib/exhaustive";
import { Badge } from "@/components/ui/badge";

/** FR-019: one badge per card, rendered exhaustively, and a tag with no label rendered raw. */
export function SeparatingBadge({ badge }: { badge: Badgeable }) {
  switch (badge.tag) {
    case "sold-at-the-end":
      return (
        <Badge tone="assume" data-separating="sold-at-the-end">
          sold at the window&apos;s end, {day(badge.on)}
        </Badge>
      );
    case "closed-by-its-own-terms":
      return (
        <Badge tone="assume" data-separating="closed-by-its-own-terms">
          its own terms closed it inside the window; the proceeds sit as cash under the declared
          continuation assumption
        </Badge>
      );
    case "unlabelled":
      return (
        <Badge tone="assume" data-separating="unlabelled">
          {badge.raw}
        </Badge>
      );
  }
  assertNever(badge);
}
