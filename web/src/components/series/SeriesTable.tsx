import type { StalenessVerdict } from "@/api/shapes";
import { marksOf } from "@/lib/provenance";
import { Table, Td, Th } from "@/components/ui/table";
import { Marks } from "@/components/figure/Mark";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { plotted } from "./points";
import type { SeriesIdentity } from "./identity";

/**
 * FR-032, FR-041: the same rows as the chart, keyboard-reachable, each carrying its own point's
 * mark. A chart is an approximation of a table here, not the other way round.
 */
export function SeriesTable({
  observations,
  identity,
  verdict,
}: {
  observations: readonly unknown[];
  identity: SeriesIdentity;
  verdict?: StalenessVerdict | undefined;
}) {
  const drawable = plotted(observations);
  if (drawable.tag === "not-a-series") {
    return <p data-table="refused">not tabulated as a series: {drawable.reason}</p>;
  }
  if (drawable.points.length === 0) {
    return (
      <p data-table="empty" className="text-sm">
        no observation was returned for this window.
      </p>
    );
  }
  return (
    <Table caption={`${identity.title} — values in ${identity.valuesIn}`}>
      <thead>
        <tr>
          <Th>{identity.axis}</Th>
          <Th>value ({identity.valuesIn})</Th>
          <Th>marks</Th>
        </tr>
      </thead>
      <tbody>
        {drawable.points.map((point) => {
          const marks = marksOf(point.observation.provenance, verdict);
          return (
            <tr key={point.at} tabIndex={0} data-row={point.at}>
              <Td>{point.at}</Td>
              <Td>
                <FigureSlot
                  state={
                    marks.length === 0
                      ? { kind: "value", figure: String(point.value) }
                      : { kind: "marked", figure: String(point.value), marks }
                  }
                />
              </Td>
              <Td>{marks.length === 0 ? "none" : <Marks marks={marks} />}</Td>
            </tr>
          );
        })}
      </tbody>
    </Table>
  );
}
