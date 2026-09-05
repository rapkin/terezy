import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { categoryQuery, registryQuery } from "@/api/queries";
import { isListing, isRecordRead } from "@/lib/narrow";
import { RecordList } from "@/components/category/RecordList";
import { RecordCard } from "@/components/record/RecordCard";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { rootRoute } from "./root";
import { Awaiting, useAsOf } from "./read";
import { policyIn } from "./policy";

/**
 * FR-015: one route for every category, and no category id, label or branch in it.
 *
 * Which of the two shapes came back is read off the body's own tag -- a listing of ids, or a
 * single document -- so a category added under `data/` and exposed by the API appears here with
 * no client change.
 */
export const categoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data/$category",
  component: CategoryScreen,
});

function CategoryScreen() {
  const { category } = categoryRoute.useParams();
  const asOf = useAsOf();
  const answered = useQuery({
    ...categoryQuery(category, asOf ?? ""),
    enabled: asOf !== undefined,
  });
  const registry = useQuery({ ...registryQuery(asOf ?? ""), enabled: asOf !== undefined });
  const policy = policyIn(registry.data, category);
  if (asOf === undefined) return null;
  if (answered.data === undefined) return <Awaiting what={category} query={answered} />;
  const body = answered.data.tag === "body" ? answered.data.body : undefined;
  if (isListing(body)) {
    return (
      <section className="space-y-3">
        <h2 className="text-base font-semibold">{category}</h2>
        <RecordList listing={body} />
      </section>
    );
  }
  if (isRecordRead(body)) return <RecordCard read={body} policy={policy} />;
  return <ApiErrorState answered={answered.data} what={category} />;
}
