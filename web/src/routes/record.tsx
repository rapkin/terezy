import { createRoute } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { recordQuery, registryQuery } from "@/api/queries";
import { isRecordRead } from "@/lib/narrow";
import { RecordCard } from "@/components/record/RecordCard";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { rootRoute } from "./root";
import { Awaiting, useAsOf } from "./read";
import { policyIn } from "./policy";

/** A record is identified by the pair `(category, id)`, never by an id alone (*Edge Cases*). */
export const recordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/data/$category/$recordId",
  component: RecordScreen,
});

function RecordScreen() {
  const { category, recordId } = recordRoute.useParams();
  const asOf = useAsOf();
  const answered = useQuery({
    ...recordQuery(category, recordId, asOf ?? ""),
    enabled: asOf !== undefined,
  });
  const registry = useQuery({ ...registryQuery(asOf ?? ""), enabled: asOf !== undefined });
  const policy = policyIn(registry.data, category);
  if (asOf === undefined) return null;
  if (answered.data === undefined) {
    return <Awaiting what={`${category}/${recordId}`} query={answered} />;
  }
  const body = answered.data.tag === "body" ? answered.data.body : undefined;
  if (!isRecordRead(body)) {
    return <ApiErrorState answered={answered.data} what={`${category}/${recordId}`} />;
  }
  return <RecordCard read={body} policy={policy} />;
}
