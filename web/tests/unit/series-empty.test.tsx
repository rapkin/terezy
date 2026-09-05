import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SeriesChart } from "@/components/series/SeriesChart";
import { SeriesTable } from "@/components/series/SeriesTable";

const IDENTITY = { title: "a series", valuesIn: "previous month = 100", axis: "period" };

/**
 * FR-008 names "an empty series in this position" among the renderings a refusal may not take.
 * A chart with axes and no points, beside a note saying every period was checked, is that
 * rendering arrived at from the other direction, so both components say so instead.
 */
describe("a window the API returned nothing for", () => {
  it("is a stated fact on the chart rather than axes with no points", () => {
    const { container } = render(
      <SeriesChart observations={[]} missing={[]} identity={IDENTITY} />,
    );
    expect(container.querySelector("[data-chart='drawn']")).toBeNull();
    expect(container.querySelector("[data-chart='empty']")?.textContent).toContain(
      "no observation",
    );
  });

  it("is a stated fact on the table rather than a header with no rows", () => {
    const { container } = render(<SeriesTable observations={[]} identity={IDENTITY} />);
    expect(container.querySelectorAll("tbody tr")).toHaveLength(0);
    expect(container.querySelector("[data-table='empty']")?.textContent).toContain(
      "no observation",
    );
  });
});
