import type { FieldDescription, StalenessVerdict } from "@/api/shapes";
import { FieldValue } from "./FieldValue";

/**
 * FR-016, FR-017: one field of a record -- its label, what it holds, and the value itself with
 * whatever provenance the value carries.
 *
 * The label is the API's own field name, untranslated (clarification Q1), so a person reading a
 * card and a person reading the TOML file see the same word and no key file exists to drift.
 */
export function FieldRow({
  field,
  value,
  verdict,
}: {
  field: FieldDescription;
  value: unknown;
  verdict?: StalenessVerdict | undefined;
}) {
  return (
    <div data-field={field.name} className="py-2">
      <dt className="flex flex-wrap items-baseline gap-2">
        <span className="font-medium">{field.name}</span>
        <span className="text-xs text-[var(--ink-muted)]">
          {field.kind}
          {field.of.length === 0 ? "" : ` of ${field.of.join(" | ")}`}
          {field.optional ? " · optional" : ""}
        </span>
      </dt>
      <dd className="mt-1">
        <FieldValue value={value} verdict={verdict} />
      </dd>
    </div>
  );
}
