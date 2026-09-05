import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { registryQuery } from "@/api/queries";
import { isRegistry } from "@/lib/narrow";
import { CategoryIndex } from "@/components/category/CategoryIndex";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { rootRoute } from "./root";
import { Awaiting, useAsOf } from "./read";

export const overviewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Overview,
});

function Overview() {
  const asOf = useAsOf();
  const answered = useQuery({ ...registryQuery(asOf ?? ""), enabled: asOf !== undefined });
  if (asOf === undefined) return null;
  if (answered.data === undefined) return <Awaiting what="the registry" query={answered} />;
  if (answered.data.tag !== "body" || !isRegistry(answered.data.body)) {
    return <ApiErrorState answered={answered.data} what="the registry" />;
  }
  return <CategoryIndex registry={answered.data.body} />;
}
