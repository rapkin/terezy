import type { QueryClient } from "@tanstack/react-query";
import {
  Link,
  Outlet,
  createRootRouteWithContext,
  redirect,
  useNavigate,
  useSearch,
} from "@tanstack/react-router";
import { today } from "@/clock";
import { parseAsOf, stringOrUndefined } from "@/search/params";
import { AppShell } from "@/components/shell/AppShell";
import { AsOfControl } from "@/components/shell/AsOfControl";
import { ParameterError } from "@/components/shell/ParameterError";
import { SERIES } from "./series-map";

export type RootSearch = { as_of?: string };

/**
 * FR-021: there is no implicit `as_of`.
 *
 * A first load without one reads the browser clock **once**, redirects with it written into the
 * URL, and renders nothing until it is there -- so every screen the owner can look at or send to
 * somebody is explicit about the date it was read at, and every later render is a function of
 * the URL rather than of the clock.
 */
export const rootRoute = createRootRouteWithContext<{ queryClient: QueryClient }>()({
  validateSearch: (search: Record<string, unknown>): RootSearch => ({
    as_of: stringOrUndefined(search["as_of"]),
  }),
  beforeLoad: ({ search, location }) => {
    if (search.as_of !== undefined) return;
    const query = new URLSearchParams(location.searchStr.replace(/^\?/, ""));
    query.set("as_of", today());
    throw redirect({ href: `${location.pathname}?${query.toString()}`, replace: true });
  },
  component: RootLayout,
});

function RootLayout() {
  const search: RootSearch = useSearch({ strict: false });
  const navigate = useNavigate();
  const parsed = parseAsOf(search.as_of);
  // Each link carries `as_of` and nothing else: a window belongs to the series it was read for,
  // and carrying one across would be a window the reader never chose, arriving already valid so
  // the destination's coverage redirect never fires (FR-027a).
  const nav = (
    <>
      <Link to="/" search={{ as_of: search.as_of }} className="underline">
        overview
      </Link>
      {SERIES.map((series) => (
        <Link key={series.to} to={series.to} search={{ as_of: search.as_of }} className="underline">
          {series.label}
        </Link>
      ))}
    </>
  );
  const control =
    parsed.tag === "given" ? (
      <AsOfControl
        asOf={parsed.value}
        onChange={(next) => {
          void navigate({ to: ".", search: (prev) => ({ ...prev, as_of: next }) });
        }}
      />
    ) : undefined;
  return (
    <AppShell nav={nav} control={control}>
      {parsed.tag === "invalid" ? <ParameterError parsed={parsed} /> : <Outlet />}
    </AppShell>
  );
}
