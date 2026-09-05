import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SeriesChart } from "@/components/series/SeriesChart";
import { identityOf } from "@/components/series/identity";
import { cpiObservation, provenance, rateObservation, source } from "../fixtures";

const CPI = identityOf({
  tag: "series.CpiSeries",
  id: "ua_cpi_monthly",
  country: "UA",
  index: "consumer price index, all goods and services",
  periodicity: "monthly",
  base: "previous month = 100",
  observations: [],
});

const RATE = identityOf({
  tag: "official_rate.OfficialRateSeries",
  id: "ua_nbu_usd",
  authority: "Національний банк України",
  pair: ["UAH", "USD"],
  quotation_unit: 1,
  rule: null,
  observations: [],
});

describe("SeriesChart", () => {
  it("plots exactly the observations returned (FR-028)", () => {
    const { container } = render(
      <SeriesChart
        observations={[cpiObservation("2025-08", 100.1), cpiObservation("2025-09", 100.4)]}
        missing={[]}
        identity={CPI}
      />,
    );
    const figure = container.querySelector("[data-chart='drawn']");
    expect(figure?.getAttribute("data-points")).toBe("2");
    expect(figure?.getAttribute("data-segments")).toBe("1");
  });

  it("draws a named gap as a break with its own label, never a line across it (FR-028)", () => {
    const { container } = render(
      <SeriesChart
        observations={[
          cpiObservation("2025-08", 100.1),
          cpiObservation("2025-10", 100.9),
        ]}
        missing={["2025-09"]}
        identity={CPI}
      />,
    );
    const figure = container.querySelector("[data-chart='drawn']");
    expect(figure?.getAttribute("data-breaks")).toBe("1");
    expect(figure?.getAttribute("data-segments")).toBe("0");
    expect(container.querySelector("[data-chart-breaks='named']")?.textContent).toContain("2025-09");
  });

  it("states the API's declared identity and what the values are in, never bare (FR-030)", () => {
    const cpi = render(
      <SeriesChart observations={[cpiObservation("2025-09", 100.4)]} missing={[]} identity={CPI} />,
    );
    expect(cpi.container.textContent).toContain("previous month = 100");
    expect(cpi.container.textContent).toContain("consumer price index");
    cpi.unmount();

    const rate = render(
      <SeriesChart observations={[rateObservation("2026-08-31", 41.2)]} missing={[]} identity={RATE} />,
    );
    expect(rate.container.textContent).toContain("UAH per 1 USD");
    expect(rate.container.textContent).toContain("Національний банк України");
  });

  it("renders a one-observation series as one point and zero segments (FR-031, SC-008)", () => {
    const { container } = render(
      <SeriesChart observations={[rateObservation("2026-08-31", 41.2)]} missing={[]} identity={RATE} />,
    );
    const figure = container.querySelector("[data-chart='drawn']");
    expect(figure?.getAttribute("data-points")).toBe("1");
    expect(figure?.getAttribute("data-segments")).toBe("0");
    const curves = [...container.querySelectorAll(".recharts-line-curve")];
    for (const curve of curves) {
      expect(curve.getAttribute("d") ?? "").not.toContain("L");
    }
  });

  it("refuses to chart a retrieval, which is not a series (FR-031a)", () => {
    const { container } = render(
      <SeriesChart
        observations={[
          {
            tag: "observations.InzhurQuotation",
            buy: 1,
            sell: 2,
            retrieved_on: "2026-09-01",
            provenance: provenance([source()]),
          },
        ]}
        missing={[]}
        identity={RATE}
      />,
    );
    expect(container.querySelector("[data-chart='refused']")?.textContent).toContain(
      "when somebody looked",
    );
    expect(container.querySelector("[data-chart='drawn']")).toBeNull();
  });

  it("renders no chart at all where the API returned nothing for the window (FR-008)", () => {
    const { container } = render(<SeriesChart observations={[]} missing={[]} identity={CPI} />);
    expect(container.querySelector("[data-chart='drawn']")).toBeNull();
    expect(container.querySelector("[data-chart='empty']")).not.toBeNull();
  });

  it("does not break past the last observation: a coverage refusal says that instead (FR-029)", () => {
    const { container } = render(
      <SeriesChart
        observations={[cpiObservation("2025-09", 100.4), cpiObservation("2025-10", 100.9)]}
        missing={["2025-11", "2025-12"]}
        identity={CPI}
      />,
    );
    expect(container.querySelector("[data-chart='drawn']")?.getAttribute("data-breaks")).toBe("0");
  });
});
