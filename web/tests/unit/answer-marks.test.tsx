import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { join } from "node:path";
import { AllMoneyBackFigure } from "@/answer/all-money-back";
import { AnswerHeader } from "@/answer/components/AnswerHeader";
import { CandidateCard } from "@/answer/components/CandidateCard";
import { FullRanking } from "@/answer/components/FullRanking";
import { MoneyBack } from "@/answer/components/MoneyBack";
import { code, modulesUnder, relativeToSrc, SRC } from "../source";
import { money, provenance, source, verdict } from "../fixtures";
import { comparison, outcome, question } from "../answer-fixtures";

/**
 * Principle I, enumerated rather than reviewed: a figure this screen renders wears its parents'
 * marks.
 *
 * 021's SC-002 does the same over `src/components`, and does not reach here — so a component
 * added under `src/answer` with a figure slot and no mark would pass every test in this tree.
 * The inventory is discovered from the source and checked against the cases below, so adding one
 * fails here until it has a case.
 */
const BEARS_A_FIGURE = /<FigureSlot/;

const DISCOVERED = modulesUnder(join(SRC, "answer"))
  .filter((path) => BEARS_A_FIGURE.test(code(path)))
  .map(relativeToSrc)
  .sort();

const UNVERIFIED = money(50529.090769230774, [source({ verified_on: null })]);
const READ = { tag: "read" as const, kind: "bond" as const, declaredClass: "enumerated_schedule" };
const MARKED = outcome({ instrumentId: "A", reaches: UNVERIFIED });

const CASES: Readonly<Record<string, ReactElement>> = {
  "answer/all-money-back.tsx": <AllMoneyBackFigure outcome={MARKED} />,
  "answer/components/AnswerHeader.tsx": (
    <AnswerHeader
      answer={{
        tag: "answer.Answer",
        as_of: "2026-09-05",
        question: question({ amounts: { salary_uah: UNVERIFIED } }),
        subjects: [],
        sections: [],
        excludes: [],
        provenance: provenance([source()]),
        staleness: verdict([]),
      }}
    />
  ),
  "answer/components/CandidateCard.tsx": (
    <CandidateCard outcome={MARKED} reading={READ} shared={[]} indistinguishable={undefined} />
  ),
  "answer/components/FullRanking.tsx": (
    <FullRanking comparison={comparison({ ranked: [MARKED] })} />
  ),
  "answer/components/MoneyBack.tsx": <MoneyBack outcome={MARKED} />,
};

describe("every figure this screen renders carries its marks", () => {
  it("enumerates the figure-bearing modules, and the inventory covers exactly them", () => {
    expect(DISCOVERED.length).toBeGreaterThan(0);
    expect(DISCOVERED).toEqual(Object.keys(CASES).sort());
  });

  for (const [module, element] of Object.entries(CASES)) {
    it(`${module} marks a figure whose provenance marks it`, () => {
      const { container } = render(element);
      expect(container.querySelector("[data-figure='marked']")).not.toBeNull();
      expect(container.textContent).toContain("unverified");
    });
  }
});
