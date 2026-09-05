import type { ReactNode } from "react";
import { render, waitFor } from "@testing-library/react";
import {
  RouterProvider,
  createMemoryHistory,
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";

/**
 * A router around one node, for the components that render `Link`s.
 *
 * The paths below are the ones those links name; nothing else about the real route tree is
 * needed, and building it here would make a component test a test of the tree.
 */
export async function renderInRouter(node: ReactNode) {
  const rootRoute = createRootRoute({ component: () => node });
  const children = ["/", "/data/$category", "/data/$category/$recordId"].map((path) =>
    createRoute({ getParentRoute: () => rootRoute, path, component: () => null }),
  );
  const router = createRouter({
    routeTree: rootRoute.addChildren(children),
    history: createMemoryHistory({ initialEntries: ["/"] }),
  });
  const view = render(<RouterProvider router={router} />);
  await waitFor(() => {
    if (view.container.textContent === "") throw new Error("the router has not rendered yet");
  });
  return view;
}
