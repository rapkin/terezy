import { rootRoute } from "./root";
import { overviewRoute } from "./overview";
import { dataIndexRoute } from "./data-index";
import { categoryRoute } from "./category";
import { recordRoute } from "./record";
import { seriesRoutes } from "./series";
import { cardRoute } from "@/card/components/CardRoute";

export const routeTree = rootRoute.addChildren([
  overviewRoute,
  dataIndexRoute,
  categoryRoute,
  recordRoute,
  ...seriesRoutes,
  cardRoute,
]);
