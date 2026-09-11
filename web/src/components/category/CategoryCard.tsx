import { Link } from "@tanstack/react-router";
import type { CategorySummary } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";
import { Card, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CitationPolicyNote } from "@/components/figure/CitationExemption";

/**
 * FR-014: what the API reports for one category -- a record count where it is keyed, a resolved
 * statement where it is a singleton.
 *
 * The two are different facts and rendering a singleton as `0` is the `B10` collapse between
 * *empty* and *absent*, on the one screen whose job is to say what the registry holds.
 */
export function CategoryCard({ summary, asOf }: { summary: CategorySummary; asOf: string }) {
  return (
    <Card>
      <CardTitle>
        <Link
          to="/data/$category"
          params={{ category: summary.category }}
          search={{ as_of: asOf }}
          className="underline"
        >
          {summary.category}
        </Link>
      </CardTitle>
      <p className="font-mono text-xs text-[var(--ink-muted)]">{summary.directory}</p>
      <p className="mt-1 text-sm">
        <Shape summary={summary} />
      </p>
      <p className="mt-1 text-sm">
        <Mark mark={summary.mark} />
      </p>
      <CitationPolicyNote policy={summary.citations} />
      <details className="mt-2 text-xs">
        <summary className="cursor-pointer">declaring files</summary>
        <ul className="mt-1 space-y-0.5 font-mono">
          {summary.files.map((file) => (
            <li key={file.file}>
              {file.file} · {file.version}
            </li>
          ))}
        </ul>
      </details>
    </Card>
  );
}

function Shape({ summary }: { summary: CategorySummary }) {
  switch (summary.tag) {
    case "summary.KeyedSummary":
      return (
        <span data-shape="keyed">keyed by id · {summary.declared_ids} declared</span>
      );
    case "summary.SingletonSummary":
      return (
        <span data-shape="singleton">
          a single document · {summary.resolved ? "resolved" : "not resolved"}
        </span>
      );
  }
  assertNever(summary);
}

/**
 * The fold's verdict, rendered as the arm the API sent.
 *
 * The sources themselves are at `/api/registry/sources`, which this page never asks for.
 */
function Mark({ mark }: { mark: CategorySummary["mark"] }) {
  switch (mark.tag) {
    case "summary.NoSourceCited":
      return (
        <Badge tone="neutral" data-category-mark="no-source-cited">
          no cited source
        </Badge>
      );
    case "summary.SourcesUnverified":
      return (
        <Badge tone="warn" data-category-mark="unverified">
          {mark.unverified} of {mark.sources} source{mark.sources === 1 ? "" : "s"} unverified ·
          retrieved by {mark.latest_retrieved_on}
        </Badge>
      );
    case "summary.EverySourceVerified":
      return (
        <Badge tone="neutral" data-category-mark="verified">
          {mark.sources} source{mark.sources === 1 ? "" : "s"}, verified since{" "}
          {mark.earliest_verified_on}
        </Badge>
      );
  }
  assertNever(mark);
}
