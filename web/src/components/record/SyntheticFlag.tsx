import { Badge } from "@/components/ui/badge";

/**
 * FR-019: the synthetic flag is rendered on the record, never left to be inferred from a
 * directory name.
 */
export function SyntheticFlag({ synthetic }: { synthetic: boolean }) {
  return (
    <Badge tone={synthetic ? "warn" : "neutral"} data-synthetic={String(synthetic)}>
      {synthetic ? "synthetic — declared, not a real security" : "not synthetic"}
    </Badge>
  );
}
