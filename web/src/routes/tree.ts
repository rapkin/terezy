import { rootRoute } from "./root";
import { overviewRoute } from "./overview";
import { categoryRoute } from "./category";
import { recordRoute } from "./record";
import { seriesRoutes } from "./series";

export const routeTree = rootRoute.addChildren([
  overviewRoute,
  categoryRoute,
  recordRoute,
  ...seriesRoutes,
]);
