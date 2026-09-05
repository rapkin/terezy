import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { join } from "node:path";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { FieldValue } from "@/components/record/FieldValue";
import { SeriesChart } from "@/components/series/SeriesChart";
import { SeriesTable } from "@/components/series/SeriesTable";
import { code, modulesUnder, relativeToSrc, SRC } from "../source";
import { cpiObservation, money, source } from "../fixtures";

/**
 * SC-002, by enumerating the figure-bearing components rather than by review.
 *
 * "Figure-bearing" is discovered from the tree, not listed: a module that renders a figure slot,
 * the slot itself, or a chart -- a figure slot whose figure is a picture. `Refusal` and `Mark`
 * are not on it because they *are* those states, and demanding a refused arm on a refusal is the
 * enumeration eating itself. A component added with a figure slot and no refused arm fails here,
 * which is the whole point of enumerating rather than reviewing.
 */
const BEARS_A_FIGURE = /<FigureSlot|export function FigureSlot|data-chart=/;

const DISCOVERED = modulesUnder(join(SRC, "components"))
  .filter((path) => BEARS_A_FIGURE.test(code(path)))
  .map(relativeToSrc)
  .sort();

const IDENTITY = { title: "a series", valuesIn: "previous month = 100", axis: "period" };

const REFUSAL = {
  tag: "envelopes.NothingDeclared" as const,
  category: "spendable",
  reason: "nothing under spendable declares a document for this owner.",
};

const CASES: Readonly<Record<string, { refused: ReactElement; marked: ReactElement }>> = {
  "components/figure/FigureSlot.tsx": {
    refused: <FigureSlot state={{ kind: "refused", refusal: REFUSAL }} />,
    marked: (
      <FigureSlot
        state={{ kind: "marked", figure: "1000 UAH", marks: [{ tag: "unverified", source: source() }] }}
      />
    ),
  },
  "components/record/FieldValue.tsx": {
    refused: <FieldValue value={REFUSAL} />,
    marked: <FieldValue value={money(1000, [source()])} />,
  },
  "components/series/SeriesChart.tsx": {
    refused: (
      <SeriesChart
        observations={[{ tag: "observations.Retrieval", retrieved_on: "2026-09-01" }]}
        missing={[]}
        identity={IDENTITY}
      />
    ),
    marked: <SeriesChart observations={[cpiObservation("2025-09", 100.4)]} missing={[]} identity={IDENTITY} />,
  },
  "components/series/SeriesTable.tsx": {
    refused: (
      <SeriesTable
        observations={[{ tag: "observations.Retrieval", retrieved_on: "2026-09-01" }]}
        identity={IDENTITY}
      />
    ),
    marked: <SeriesTable observations={[cpiObservation("2025-09", 100.4)]} identity={IDENTITY} />,
  },
};

describe("every figure-bearing component has a refused state and a marked state", () => {
  it("enumerates the ones in the tree, and the inventory covers exactly them", () => {
    expect(DISCOVERED.length).toBeGreaterThan(0);
    expect(DISCOVERED).toEqual(Object.keys(CASES).sort());
  });

  for (const [module, states] of Object.entries(CASES)) {
    it(`${module} refuses rather than rendering a placeholder`, () => {
      const { container } = render(states.refused);
      const text = container.textContent ?? "";
      expect(text.trim()).not.toBe("");
      expect(["0", "—", "n/a", "N/A"]).not.toContain(text.trim());
      expect(container.querySelector("[data-figure='refused'], [data-chart='refused'], [data-table='refused']")).not.toBeNull();
    });

    it(`${module} marks a figure whose provenance marks it`, () => {
      const { container } = render(states.marked);
      expect(container.textContent).toContain("unverified");
    });
  }
});
