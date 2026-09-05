import type { RegistrySummary } from "@/api/shapes";
import { CategoryCard } from "./CategoryCard";

/**
 * FR-015: no category id, label or per-category branch appears here. The index is the list, so a
 * category added under `data/` and exposed by the API arrives with no client change.
 */
export function CategoryIndex({ registry }: { registry: RegistrySummary }) {
  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--ink-muted)]">
        the categories the registry indexes, read as of {registry.as_of} under scenario{" "}
        {registry.scenario_id ?? "none in force"}
      </p>
      <ul className="grid gap-3 sm:grid-cols-2">
        {registry.categories.map((summary) => (
          <li key={summary.category}>
            <CategoryCard summary={summary} asOf={registry.as_of} />
          </li>
        ))}
      </ul>
    </div>
  );
}
