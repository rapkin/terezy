import { CartesianGrid, Line, LineChart, XAxis, YAxis } from "recharts";
import type { StalenessVerdict } from "@/api/shapes";
import { marksOf, type Mark } from "@/lib/provenance";
import { Marks } from "@/components/figure/Mark";
import type { SeriesIdentity } from "./identity";
import { cells, plotted, segments, type Point } from "./points";

/**
 * FR-028, FR-030, FR-031, FR-031a.
 *
 * Plots exactly the observations returned. A named gap is a break with its own label and never a
 * straight line between the two points around it; the axes state the API's declared identity and
 * what the values are in; a one-observation series is one point and zero segments; and a
 * retrieval refuses instead of being charted.
 */
export function SeriesChart({
  observations,
  missing,
  identity,
  verdict,
  width = 720,
  height = 280,
}: {
  observations: readonly unknown[];
  missing: readonly string[];
  identity: SeriesIdentity;
  verdict?: StalenessVerdict;
  width?: number;
  height?: number;
}) {
  const drawable = plotted(observations);
  if (drawable.tag === "not-a-series") {
    return (
      <p
        data-chart="refused"
        className="rounded border border-[var(--refuse-border)] bg-[var(--refuse-surface)] p-2 text-sm text-[var(--refuse-ink)]"
      >
        not charted: {drawable.reason}
      </p>
    );
  }
  if (drawable.points.length === 0) {
    return (
      <p data-chart="empty" className="text-sm">
        no observation was returned for this window, so nothing is drawn — a chart of no points is
        a series with nothing in it.
      </p>
    );
  }
  const rows = cells(drawable.points, missing);
  const breaks = rows.filter((row) => row.value === null);
  const marks = distinctMarks(drawable.points, verdict);
  return (
    <figure
      data-chart="drawn"
      data-points={String(drawable.points.length)}
      data-segments={String(segments(rows))}
      data-breaks={String(breaks.length)}
      data-figure={marks.length === 0 ? "value" : "marked"}
    >
      <figcaption className="text-sm">
        {identity.title} · values in {identity.valuesIn} · keyed by {identity.axis}
        {marks.length > 0 && (
          <span>
            {" "}
            — the plotted observations carry
            <Marks marks={marks} />, and the table below carries each point's own
          </span>
        )}
      </figcaption>
      <LineChart width={width} height={height} data={[...rows]} aria-hidden="true">
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="at" label={{ value: identity.axis, position: "insideBottom" }} />
        <YAxis label={{ value: identity.valuesIn, angle: -90, position: "insideLeft" }} />
        <Line
          type="linear"
          dataKey="value"
          connectNulls={false}
          isAnimationActive={false}
          stroke="var(--accent)"
          dot
        />
      </LineChart>
      {breaks.length > 0 && (
        <ul data-chart-breaks="named" className="mt-1 text-xs text-[var(--warn-ink)]">
          {breaks.map((row) => (
            <li key={row.at}>break at {row.at} — the API declares no observation for it</li>
          ))}
        </ul>
      )}
    </figure>
  );
}

/**
 * One mark of each kind the plotted points carry.
 *
 * A summary beside the chart and never instead of the per-point marks: FR-032's table renders
 * those, and FR-011 permits a summary only where it does not replace them.
 */
function distinctMarks(points: readonly Point[], verdict: StalenessVerdict | undefined): readonly Mark[] {
  const byTag = new Map<Mark["tag"], Mark>();
  for (const point of points) {
    for (const mark of marksOf(point.observation.provenance, verdict)) {
      if (!byTag.has(mark.tag)) byTag.set(mark.tag, mark);
    }
  }
  return [...byTag.values()];
}
