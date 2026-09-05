import { createRoute, redirect } from "@tanstack/react-router";
import { useQuery } from "@tanstack/react-query";
import { categoryQuery, observationsQuery, recordQuery } from "@/api/queries";
import { isRecord, isRecordRead, isSeriesListing, isSeriesWindow } from "@/lib/narrow";
import { isRefusal } from "@/lib/provenance";
import { parseAsOf, parseWindow, stringOrUndefined } from "@/search/params";
import { identityOf } from "@/components/series/identity";
import { isSeriesRecord } from "@/components/series/record";
import { SeriesChart } from "@/components/series/SeriesChart";
import { SeriesTable } from "@/components/series/SeriesTable";
import { CoverageRefusal } from "@/components/series/CoverageRefusal";
import { Refusal } from "@/components/figure/Refusal";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { ParameterError } from "@/components/shell/ParameterError";
import { rootRoute } from "./root";
import { Awaiting, useAsOf, useWindow } from "./read";
import { SERIES, type SeriesRoute } from "./series-map";

type SeriesSearch = { from?: string; to?: string };

/**
 * FR-027a: no implicit window.
 *
 * A route loaded without one asks the API for the series' declared coverage, redirects with it
 * written into the URL, and renders from there. The client chooses no window and falls back to
 * no "recent" and no fixed span -- the rate series is one observation per calendar day over
 * years, so a client-chosen span would be a client-chosen truncation.
 */
function seriesRoute(declared: SeriesRoute) {
  return createRoute({
    getParentRoute: () => rootRoute,
    path: declared.to,
    validateSearch: (search: Record<string, unknown>): SeriesSearch => ({
      from: stringOrUndefined(search["from"]),
      to: stringOrUndefined(search["to"]),
    }),
    loaderDeps: ({ search }) => ({ ...search }),
    loader: async ({ context, deps, location }) => {
      const asOf = parseAsOf(stringOrUndefined(deps["as_of"]));
      if (asOf.tag !== "given") return;
      if (parseWindow(deps.from, deps.to).tag !== "missing") return;
      const listing = await context.queryClient.query(
        categoryQuery(declared.category, asOf.value),
      );
      const declaredWindow = coverageOf(listing.tag === "body" ? listing.body : undefined);
      if (declaredWindow === null) return;
      const query = new URLSearchParams(location.searchStr.replace(/^\?/, ""));
      query.set("from", declaredWindow.first);
      query.set("to", declaredWindow.last);
      throw redirect({ href: `${location.pathname}?${query.toString()}`, replace: true });
    },
    component: () => <SeriesScreen declared={declared} />,
  });
}

/** The two routes FR-015a names, and there are exactly two. */
export const seriesRoutes = SERIES.map(seriesRoute);

/**
 * The one series a routed category declares, and its coverage.
 *
 * `null` where the category declares anything but exactly one: which of two the route meant is
 * not a question the client may answer for it (FR-001).
 */
function coverageOf(body: unknown): { first: string; last: string; id: string } | null {
  if (!isSeriesListing(body) || body.ids.length !== 1) return null;
  const only = body.ids[0] ?? "";
  const coverage: unknown = isRecord(body.coverage) ? body.coverage[only] : undefined;
  if (!isRecord(coverage)) return null;
  const first = coverage["first"];
  const last = coverage["last"];
  if (typeof first !== "string" || typeof last !== "string") return null;
  return { first, last, id: only };
}

function SeriesScreen({ declared }: { declared: SeriesRoute }) {
  const asOf = useAsOf();
  const window = useWindow();
  const listing = useQuery({
    ...categoryQuery(declared.category, asOf ?? ""),
    enabled: asOf !== undefined,
  });
  const only = coverageOf(listing.data?.tag === "body" ? listing.data.body : undefined);
  const seriesId = only?.id ?? "";
  const record = useQuery({
    ...recordQuery(declared.category, seriesId, asOf ?? ""),
    enabled: asOf !== undefined && seriesId !== "",
  });
  const observations = useQuery({
    ...observationsQuery(
      declared.category,
      seriesId,
      asOf ?? "",
      window.tag === "given" ? window.value : { from: "", to: "" },
    ),
    enabled: asOf !== undefined && seriesId !== "" && window.tag === "given",
  });

  if (asOf === undefined) return null;
  if (window.tag === "invalid") return <ParameterError parsed={window} />;
  if (listing.data === undefined) return <Awaiting what={declared.label} query={listing} />;
  const listed = listing.data.tag === "body" ? listing.data.body : undefined;
  if (!isSeriesListing(listed)) {
    return <ApiErrorState answered={listing.data} what={declared.category} />;
  }
  if (only === null) {
    return (
      <p role="alert" data-series="not-one">
        the category {declared.category} declares {listed.ids.join(", ") || "no series"}, and this
        route names one of them. Which of several to draw is not a choice this client makes.
      </p>
    );
  }
  if (window.tag === "missing") {
    return (
      <p role="status" data-series="awaiting-window">
        reading the declared coverage of {only.id} to write a window into the URL…
      </p>
    );
  }
  if (record.data === undefined) return <Awaiting what={only.id} query={record} />;
  const read = record.data.tag === "body" ? record.data.body : undefined;
  if (!isRecordRead(read) || !isSeriesRecord(read.result)) {
    return <ApiErrorState answered={record.data} what={only.id} />;
  }
  const identity = identityOf(read.result);
  if (observations.data === undefined) {
    return <Awaiting what={`observations of ${only.id}`} query={observations} />;
  }
  const windowed = observations.data.tag === "body" ? observations.data.body : undefined;
  if (!isSeriesWindow(windowed)) {
    return <ApiErrorState answered={observations.data} what={`observations of ${only.id}`} />;
  }
  const result = windowed.result;
  if (isRefusal(result)) return <Refusal refusal={result} />;

  return (
    <section className="space-y-4">
      <h2 className="text-base font-semibold">{identity.title}</h2>
      <p className="text-sm text-[var(--ink-muted)]">
        window {window.value.from} .. {window.value.to} · read as of {windowed.as_of}
      </p>
      {result.observations.length === 0 ? (
        <p role="note" data-series="no-observation">
          the API returned no observation for {window.value.from} .. {window.value.to}. Nothing is
          drawn, because a chart of no points is a series with nothing in it.
        </p>
      ) : (
        <>
          <SeriesChart
            observations={result.observations}
            missing={result.outside?.missing ?? []}
            identity={identity}
          />
          <SeriesTable observations={result.observations} identity={identity} />
        </>
      )}
      <CoverageRefusal outside={result.outside} checked={result.checked} />
    </section>
  );
}
