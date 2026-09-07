import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { HorizonColumn } from "@/answer/components/HorizonColumn";
import { GROUP, count } from "@/design/format";
import {
  comparison,
  dominance,
  noCandidate,
  outcome,
  refusedTuple,
  range,
  section,
  survey,
  tuple,
} from "../answer-fixtures";

/**
 * FR-012: every population the section reports has a count, and every count's members are one
 * interaction away.
 *
 * And a failed section is a section: the survey, the comparison and the dominance pass each
 * refuse in their own vocabulary, and a column that renders nothing looks exactly like a column
 * that failed to load.
 */
const RANKED = [
  outcome({ instrumentId: "A", span: range("2026-09-01", "2026-10-04") }),
  outcome({ instrumentId: "B", span: range("2026-09-01", "2026-09-19") }),
];

function column(over: Parameters<typeof section>[0]) {
  return render(
    <HorizonColumn section={section(over)} readings={new Map()} shared={[]} />,
  );
}

const WHOLE = {
  outcome: survey({
    comparison: comparison({ ranked: RANKED, benchmark: 1, beats: [0], refused: [refusedTuple("Z", "no terms")] }),
    noCandidates: [noCandidate("Y"), noCandidate("X")],
  }),
  dominance: dominance({ nonDominated: [tuple("A")] }),
};

describe("a horizon column", () => {
  it("shows a card for exactly the non-dominated members the API sent", () => {
    const { container } = column(WHOLE);
    const cards = container.querySelectorAll("[data-candidate]");
    expect(cards).toHaveLength(1);
    expect(cards[0]?.getAttribute("data-candidate")).toBe("A");
  });

  it("heads the column with the banner where the rows' spans differ", () => {
    expect(column(WHOLE).container.querySelector("[data-comparability-banner]")).not.toBeNull();
  });

  it("shows no banner where every row was measured over the same length", () => {
    const equal = [
      outcome({ instrumentId: "A", span: range("2026-09-01", "2026-10-01") }),
      outcome({ instrumentId: "B", span: range("2026-10-01", "2026-10-31") }),
    ];
    const { container } = column({
      outcome: survey({ comparison: comparison({ ranked: equal }) }),
      dominance: dominance({ nonDominated: [] }),
    });
    expect(container.querySelector("[data-comparability-banner]")).toBeNull();
  });

  it("states its own benchmark standing and asserts none across sections", () => {
    const { container } = column({
      ...WHOLE,
      dominance: dominance({
        nonDominated: [],
        standing: { tag: "dominance.HurdleIsDominated", key: tuple("H"), by: [] },
      }),
    });
    const standing = container.querySelector("[data-benchmark-standing]");
    expect(standing?.getAttribute("data-benchmark-standing")).toBe("dominance.HurdleIsDominated");
    expect(standing?.textContent).toContain("is dominated");
  });

  it("gives every population a count, and each count its own members", () => {
    const { container } = column(WHOLE);
    const populations = container.querySelectorAll("[data-population]");
    expect(populations.length).toBeGreaterThan(5);
    for (const held of populations) {
      const name = held.getAttribute("data-population") ?? "";
      // A folded population lists its members inside its groups; both are one interaction away.
      const members = held.querySelectorAll(
        "[data-population-members] > li, [data-group-members] > li",
      );
      expect(count(members.length), `${name} counted differently from what it holds`).toBe(
        held.getAttribute("data-count"),
      );
    }
  });

  it("resolves an index into ranked to the member it names, not merely to a member", () => {
    // `benchmark`, `beats_benchmark` and `ties` are indices. A population that counted its
    // members and never identified them stayed green with every index resolving to row zero.
    const named = (beats: readonly number[]) =>
      [
        ...column({
          ...WHOLE,
          outcome: survey({ comparison: comparison({ ranked: RANKED, beats }) }),
        }).container.querySelectorAll(
          "[data-population='beating the benchmark'] [data-ranked-member]",
        ),
      ].map((held) => held.getAttribute("data-ranked-member"));
    expect(named([1])).toEqual(["B"]);
    expect(named([0])).toEqual(["A"]);
    expect(named([1, 0])).toEqual(["B", "A"]);
  });

  it("states the front's own count and no ratio over a set the pass did not place", () => {
    // The pass places `ranked` less `arrives_after_horizon`, so "N of M ranked" invited a
    // subtraction that attributed a verdict to a row nobody assessed. Every count the section
    // reports stands beside its own members instead.
    const held = column(WHOLE).container.querySelector("[data-front-count]");
    expect(held?.getAttribute("data-front-count")).toBe("1");
    expect(held?.textContent).toBe("1 dominated by nothing");
    expect(held?.textContent).not.toContain("of");
  });

  it("renders a survey that did not run as its own reason, and no card", () => {
    const { container } = column({
      outcome: {
        tag: "candidates.CeilingExceeded",
        ceiling: 6000,
        reached: 6864,
        reason: "the pair ceiling was exceeded before anything was costed.",
      },
      dominance: dominance({ nonDominated: [] }),
    });
    const state = container.querySelector("[data-typed-state='candidates.CeilingExceeded']");
    expect(state?.textContent).toContain("the pair ceiling was exceeded");
    expect(state?.textContent).toContain(`6${GROUP}000`);
    expect(container.querySelectorAll("[data-candidate]")).toHaveLength(0);
  });

  it("renders a comparison with no benchmark as its own reason, and no card", () => {
    const { container } = column({
      outcome: {
        tag: "candidates.CandidateSurvey",
        comparison: {
          tag: "tuple.BenchmarkUnavailable",
          reason: "the benchmark instrument yielded no candidate for this horizon.",
          refusal: {
            tag: "tuple.InstrumentRefused",
            instrument_id: "UA4000231195",
            reason: "the benchmark instrument yielded no candidate for this horizon.",
          },
          scored: [],
          refused: [],
          not_comparable: [],
        },
        enumerated: surveyEnumerated(),
      },
      dominance: dominance({ nonDominated: [] }),
    });
    expect(
      container.querySelector("[data-typed-state='tuple.BenchmarkUnavailable']")?.textContent,
    ).toContain("yielded no candidate");
    expect(container.querySelectorAll("[data-candidate]")).toHaveLength(0);
  });

  it("gives that member's own populations their members, not a count inside a state", () => {
    const { container } = column({
      outcome: {
        tag: "candidates.CandidateSurvey",
        comparison: {
          tag: "tuple.BenchmarkUnavailable",
          reason: "the benchmark instrument yielded no candidate for this horizon.",
          refusal: {
            tag: "tuple.InstrumentRefused",
            instrument_id: "UA4000231195",
            reason: "the benchmark instrument yielded no candidate for this horizon.",
          },
          scored: RANKED,
          refused: [refusedTuple("Z", "no terms")],
          not_comparable: [],
        },
        enumerated: surveyEnumerated(),
      },
      dominance: dominance({ nonDominated: [] }),
    });
    const scored = container.querySelector(
      "[data-population='scored, with no benchmark to compare against']",
    );
    expect(scored?.getAttribute("data-count")).toBe("2");
    expect(scored?.querySelectorAll("[data-population-members] > li")).toHaveLength(2);
    const refused = container.querySelector("[data-population='refused']");
    expect(refused?.getAttribute("data-count")).toBe("1");
    expect(refused?.querySelectorAll("[data-group-members] > li")).toHaveLength(1);
  });

  it("renders a dominance pass that did not run as its own reason, and no card", () => {
    const { container } = column({
      outcome: survey({ comparison: comparison({ ranked: RANKED }) }),
      dominance: {
        tag: "dominance.NoSurveyToRunOver",
        refusal: {
          tag: "candidates.CeilingExceeded",
          ceiling: 6000,
          reached: 6864,
          reason: "the survey refused, so there was nothing to place.",
        },
      },
    });
    const held = container.querySelector("[data-typed-state='dominance.NoSurveyToRunOver']");
    // The member carries no reason of its own — it carries the refusal that caused it, and the
    // state names that rather than rendering an empty note.
    expect(held?.textContent).toContain("candidates.CeilingExceeded");
    expect(container.querySelectorAll("[data-candidate]")).toHaveLength(0);
  });

  it("folds the no-candidate pairs into groups and states how many pairs were considered", () => {
    const { container } = column(WHOLE);
    const held = container.querySelector("[data-population='no candidate']");
    expect(held?.getAttribute("data-count")).toBe("2");
    expect(held?.textContent).toContain("of 26 considered");
    expect(held?.querySelectorAll("[data-group-members] > li")).toHaveLength(2);
  });
});

function surveyEnumerated() {
  const built = survey({ comparison: comparison({ ranked: [] }) });
  if (built.tag !== "candidates.CandidateSurvey") throw new Error("the fixture changed shape");
  return built.enumerated;
}
