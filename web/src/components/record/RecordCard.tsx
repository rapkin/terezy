import type { CitationPolicy, RecordRead, StalenessVerdict } from "@/api/shapes";
import { isRecord } from "@/lib/narrow";
import { isRefusal, isStalenessVerdict } from "@/lib/provenance";
import { Card, CardTitle } from "@/components/ui/card";
import { Refusal } from "@/components/figure/Refusal";
import { CitationPolicyNote } from "@/components/figure/CitationExemption";
import { DeclaringPath } from "./DeclaringPath";
import { FieldRow } from "./FieldRow";
import { SyntheticFlag } from "./SyntheticFlag";

/**
 * FR-016: every field the API returns, in the order returned.
 *
 * FR-011 is why there is no summarising banner: a banner is a claim about the page, and the
 * requirement is a claim about each number on it, so a card whose every field is unverified
 * shows a mark on each of them.
 */
export function RecordCard({
  read,
  policy,
}: {
  read: RecordRead;
  policy?: CitationPolicy | undefined;
}) {
  const result: unknown = read.result;
  const verdict = verdictIn(result);
  const synthetic = syntheticIn(result);
  return (
    <Card>
      <header className="space-y-1 border-b border-[var(--border)] pb-2">
        <CardTitle>
          {read.category} · {identityOf(result) ?? "no id declared"}
        </CardTitle>
        <DeclaringPath declaredIn={read.declared_in} />
        <p className="text-xs text-[var(--ink-muted)]">
          read as of {read.as_of} · scenario {scenarioOf(read) ?? "none in force"}
        </p>
        {policy !== undefined && <CitationPolicyNote policy={policy} />}
        {synthetic !== null && <SyntheticFlag synthetic={synthetic} />}
      </header>
      {isRefusal(result) ? (
        <Refusal refusal={result} />
      ) : (
        <dl className="divide-y divide-[var(--border)]">
          {read.fields.map((field) => (
            <FieldRow
              key={field.name}
              field={field}
              value={isRecord(result) ? result[field.name] : null}
              verdict={verdict}
            />
          ))}
        </dl>
      )}
    </Card>
  );
}

function identityOf(result: unknown): string | null {
  if (!isRecord(result)) return null;
  const id = result["id"];
  return typeof id === "string" ? id : null;
}

function syntheticIn(result: unknown): boolean | null {
  if (!isRecord(result)) return null;
  const flag = result["is_synthetic"];
  return typeof flag === "boolean" ? flag : null;
}

function scenarioOf(read: RecordRead): string | null {
  const scenario: unknown = read.scenario_id;
  return typeof scenario === "string" ? scenario : null;
}

/**
 * The staleness verdict a record carries, where it carries one.
 *
 * Found rather than asked for: 020 puts a verdict on the results that have one and on no other,
 * so the alternative would be a client-side list of which categories those are.
 */
function verdictIn(result: unknown): StalenessVerdict | undefined {
  if (!isRecord(result)) return undefined;
  for (const held of Object.values(result)) {
    if (isStalenessVerdict(held)) return held;
  }
  return undefined;
}
