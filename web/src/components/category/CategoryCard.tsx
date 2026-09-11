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
        <Mark mark={summary.mark} citations={summary.citations} />
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
 *
 * **A category citing nothing is read against its own policy**, which is why the tone takes both
 * served fields: where citations are required, nothing cited is a gap and renders marked, and
 * where the directory is exempt it is the owner's own statement and renders calm. One tone for
 * both would put *nothing to verify* and *everything verified* behind one colour.
 */
function Mark({
  mark,
  citations,
}: {
  mark: CategorySummary["mark"];
  citations: CategorySummary["citations"];
}) {
  switch (mark.tag) {
    case "summary.NoSourceCited":
      return (
        <Badge
          tone={citations.tag === "citation_policy.CitationsRequired" ? "warn" : "neutral"}
          data-category-mark="no-source-cited"
        >
          no cited source
        </Badge>
      );
    case "summary.SourcesUnverified":
      return (
        <Badge tone="warn" data-category-mark="unverified">
          {mark.unverified} of {mark.sources} source{mark.sources === 1 ? "" : "s"} unverified ·{" "}
          <Retrieved mark={mark} />
        </Badge>
      );
    case "summary.EverySourceVerified":
      return (
        <Badge tone="neutral" data-category-mark="verified">
          {mark.sources} source{mark.sources === 1 ? "" : "s"}, verified since{" "}
          {mark.earliest_verified_on} · <Retrieved mark={mark} />
        </Badge>
      );
  }
  assertNever(mark);
}

/** Both ends of the retrieval span, collapsed to one date only when they are one date. */
function Retrieved({
  mark,
}: {
  mark: Extract<CategorySummary["mark"], { latest_retrieved_on: string }>;
}) {
  return (
    <span data-retrieved={`${mark.earliest_retrieved_on}..${mark.latest_retrieved_on}`}>
      {mark.earliest_retrieved_on === mark.latest_retrieved_on
        ? `retrieved ${mark.latest_retrieved_on}`
        : `retrieved ${mark.earliest_retrieved_on} – ${mark.latest_retrieved_on}`}
    </span>
  );
}
