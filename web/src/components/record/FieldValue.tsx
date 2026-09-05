import type { StalenessVerdict } from "@/api/shapes";
import { isRecord } from "@/lib/narrow";
import { isMoney, isProvenance, isRefusal, isStalenessVerdict, marksOf } from "@/lib/provenance";
import { FigureSlot, type FigureState } from "@/components/figure/FigureSlot";
import { Provenance } from "@/components/figure/Provenance";
import { LongValue } from "./LongValue";

/**
 * One declared value, rendered as it arrived.
 *
 * Generic by construction (FR-016): a shape this component has no special rendering for is shown
 * as its raw value rather than dropped, so a field the API adds appears with no client change.
 * Numbers are rendered as received -- a locale format that rounded would be the client emitting
 * a figure of its own (FR-001).
 */
export function FieldValue({
  value,
  verdict,
}: {
  value: unknown;
  verdict?: StalenessVerdict | undefined;
}) {
  if (value === null || value === undefined) {
    return <span data-value="absent">not declared</span>;
  }
  if (typeof value === "boolean") return <span data-value="boolean">{String(value)}</span>;
  if (typeof value === "number") return <span data-value="number">{String(value)}</span>;
  if (typeof value === "string") return <LongValue text={value} />;

  if (Array.isArray(value)) {
    if (value.length === 0) return <span data-value="empty-list">declared as an empty list</span>;
    return (
      <ol data-value="list" className="ml-4 list-decimal space-y-1">
        {value.map((held: unknown, at) => (
          <li key={at}>
            <FieldValue value={held} verdict={verdict} />
          </li>
        ))}
      </ol>
    );
  }

  if (isMoney(value)) {
    return (
      <div data-money={value.currency}>
        <FigureSlot state={figureFor(value, verdict)} />
        <Provenance provenance={value.provenance} verdict={verdict} />
      </div>
    );
  }
  if (isRefusal(value)) return <FigureSlot state={{ kind: "refused", refusal: value }} />;
  if (isProvenance(value)) return <Provenance provenance={value} verdict={verdict} />;
  if (isStalenessVerdict(value)) return <Staleness verdict={value} />;

  if (isRecord(value)) {
    const tag = typeof value["tag"] === "string" ? value["tag"] : null;
    const entries = Object.entries(value).filter(([name]) => name !== "tag");
    return (
      <div data-value="record" data-record-tag={tag ?? "untagged"} className="space-y-1">
        {tag !== null && <p className="font-mono text-xs text-[var(--ink-muted)]">{tag}</p>}
        <dl className="ml-3 space-y-1 border-l border-[var(--border)] pl-3">
          {entries.map(([name, held]) => (
            <div key={name}>
              <dt className="text-xs font-medium">{name}</dt>
              <dd>
                <FieldValue value={held} verdict={verdict} />
              </dd>
            </div>
          ))}
        </dl>
      </div>
    );
  }

  return <span data-value="unrepresented">{JSON.stringify(value)}</span>;
}

/** A money amount is a figure: it renders marked when its provenance marks it (FR-007). */
export function figureFor(value: unknown, verdict?: StalenessVerdict): FigureState {
  if (isRefusal(value)) return { kind: "refused", refusal: value };
  if (isMoney(value)) {
    const marks = marksOf(value.provenance, verdict);
    const figure = (
      <span>
        {String(value.amount)} {value.currency}
      </span>
    );
    return marks.length === 0 ? { kind: "value", figure } : { kind: "marked", figure, marks };
  }
  return { kind: "value", figure: <FieldValue value={value} verdict={verdict} /> };
}

function Staleness({ verdict }: { verdict: StalenessVerdict }) {
  return (
    <div data-staleness={verdict.stale.length === 0 ? "none" : "some"} className="text-xs">
      <p>assessed: {verdict.assessed.length === 0 ? "no source" : verdict.assessed.join(", ")}</p>
      {verdict.stale.length === 0 ? (
        <p>no assessed source is past its threshold</p>
      ) : (
        <ul className="ml-4 list-disc">
          {verdict.stale.map((stale) => (
            <li key={stale.source_id}>
              stale — {stale.source_id} retrieved {stale.retrieved_on}, {stale.age_days} days old
              against a {stale.threshold_days}-day threshold for {stale.kind_id},{" "}
              {stale.overdue_days} days overdue
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
