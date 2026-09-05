import type { CitationPolicy } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";

/**
 * FR-013: on a record in an exempt directory the absent citation renders as the exemption with
 * the API's own reason for it, never as an empty citation block.
 *
 * That reason is also what labels a per-owner record as the owner's **statement** rather than as
 * an observation (clarification Q3): the directory is exempt *because* it holds his statements,
 * so the label is the mechanism and not a caption added beside it.
 */
export function CitationPolicyNote({ policy }: { policy: CitationPolicy }) {
  switch (policy.tag) {
    case "citation_policy.CitationsExempt":
      return (
        <p data-citations="exempt" className="text-xs text-[var(--warn-ink)]">
          citations exempt for {policy.path} — {policy.reason}
        </p>
      );
    case "citation_policy.CitationsRequired":
      return (
        <p data-citations="required" className="text-xs text-[var(--ink-muted)]">
          citations required for {policy.path}
        </p>
      );
  }
  assertNever(policy);
}
