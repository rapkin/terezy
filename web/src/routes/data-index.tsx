import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { registryQuery } from "@/api/queries";
import { isRegistry } from "@/lib/narrow";
import { CategoryIndex } from "@/components/category/CategoryIndex";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { rootRoute } from "./root";
import { Awaiting, useAsOf } from "./read";

/**
 * 026 FR-028: 021's category index, at its own path under the browser's prefix.
 *
 * The screen is unchanged — what moved is which path serves it, because `/` now serves the
 * answer. Every other 021 route keeps its path and its meaning.
 */
export const dataIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data",
  component: DataIndex,
});

function DataIndex() {
  const asOf = useAsOf();
  const answered = useQuery({ ...registryQuery(asOf ?? ""), enabled: asOf !== undefined });
  if (asOf === undefined) return null;
  if (answered.data === undefined) return <Awaiting what="the registry" query={answered} />;
  if (answered.data.tag !== "body" || !isRegistry(answered.data.body)) {
    return <ApiErrorState answered={answered.data} what="the registry" />;
  }
  return <CategoryIndex registry={answered.data.body} />;
}
