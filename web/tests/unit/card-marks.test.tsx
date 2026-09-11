import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { join } from "node:path";
import { CandidateCard } from "@/card/components/CandidateCard";
import { TaxBar } from "@/card/components/TaxBar";
import { Waterfall } from "@/card/components/Waterfall";
import { Attribution } from "@/card/components/Attribution";
import { code, modulesUnder, relativeToSrc, SRC } from "../source";
import { money, source } from "../fixtures";
import { outcome, part } from "../answer-fixtures";
import { citedZero, projection } from "../card-fixtures";

/**
 * FR-018, enumerated rather than reviewed: every figure this card renders wears a mark.
 *
 * `answer-marks.test.tsx` makes the same claim over `src/answer` and does not reach here, so a
 * figure-bearing component added under `src/card` with an unmarked slot would pass every other
 * test in this tree. The inventory is discovered from the source and checked against the cases
 * below, so adding one fails here until it has a case.
 */
const BEARS_A_FIGURE = /<FigureSlot/;

const DISCOVERED = modulesUnder(join(SRC, "card"))
  .filter((path) => BEARS_A_FIGURE.test(code(path)))
  .map(relativeToSrc)
  .sort();

const UNVERIFIED = money(50529.090769230774, [source({ verified_on: null })]);
const MARKED = outcome({
  instrumentId: "UA4000231195",
  reaches: UNVERIFIED,
  parts: [part("entry", UNVERIFIED)],
});

const CASES: Readonly<Record<string, ReactElement>> = {
  "card/components/Attribution.tsx": <Attribution outcome={MARKED} />,
  "card/components/CandidateCard.tsx": (
    <CandidateCard projection={projection()} outcome={MARKED} />
  ),
  "card/components/TaxBar.tsx": (
    <TaxBar amount={citedZero()} base={UNVERIFIED} taxClassId="ua_government_bond" on={null} />
  ),
  "card/components/Waterfall.tsx": <Waterfall projection={projection()} outcome={MARKED} />,
};

describe("every figure this card renders carries its marks", () => {
  it("enumerates the figure-bearing modules, and the inventory covers exactly them", () => {
    expect(DISCOVERED.length).toBeGreaterThan(0);
    expect(DISCOVERED).toEqual(Object.keys(CASES).sort());
  });

  for (const [module, element] of Object.entries(CASES)) {
    it(`${module} marks every figure it renders`, () => {
      const { container } = render(element);
      const marked = [...container.querySelectorAll("[data-figure='marked']")];
      expect(marked.length).toBeGreaterThan(0);
      expect(container.querySelectorAll("[data-figure='value']")).toHaveLength(0);
      for (const slot of marked) {
        expect(slot.querySelectorAll("[data-mark]").length).toBeGreaterThan(0);
      }
    });
  }
});
