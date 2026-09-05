import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { userEvent } from "@testing-library/user-event";
import { SeriesTable } from "@/components/series/SeriesTable";
import { cpiObservation } from "../fixtures";

const CPI = {
  title: "consumer price index — UA, monthly",
  valuesIn: "previous month = 100",
  axis: "period",
};

describe("SeriesTable", () => {
  it("carries the same rows as the chart, each with its own point's mark (FR-032)", () => {
    const { container } = render(
      <SeriesTable
        observations={[cpiObservation("2025-09", 100.4), cpiObservation("2025-10", 100.9, true)]}
        identity={CPI}
      />,
    );
    const rows = [...container.querySelectorAll("tbody tr")];
    expect(rows.map((row) => row.getAttribute("data-row"))).toEqual(["2025-09", "2025-10"]);
    expect(rows[0]?.textContent).toContain("unverified");
    expect(rows[1]?.textContent).toContain("none");
  });

  it("states what the values are in, in the header (FR-030)", () => {
    const { container } = render(
      <SeriesTable observations={[cpiObservation("2025-09", 100.4)]} identity={CPI} />,
    );
    expect(container.textContent).toContain("previous month = 100");
  });

  it("is reachable by keyboard (FR-041)", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <SeriesTable observations={[cpiObservation("2025-09", 100.4)]} identity={CPI} />,
    );
    await user.tab();
    expect(document.activeElement).toBe(container.querySelector("tbody tr"));
  });
});
