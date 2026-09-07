import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CandidateCard } from "@/answer/components/CandidateCard";
import { GROUP, day, money as rendered, rate } from "@/design/format";
import { money, source } from "../fixtures";
import { SOLD_EARLY, outcome, range, tuple } from "../answer-fixtures";

/**
 * FR-015: the card's whole field order, each of `FigureSlot`'s three states, and no unrounded
 * float in what it renders.
 */
const READ = { tag: "read" as const, kind: "bond" as const, declaredClass: "enumerated_schedule" };
const REACHES = money(50529.090769230774, [source()]);

function card(over: Parameters<typeof outcome>[0], extra: Partial<Parameters<typeof CandidateCard>[0]> = {}) {
  return render(
    <CandidateCard
      outcome={outcome(over)}
      reading={READ}
      shared={[]}
      indistinguishable={undefined}
      {...extra}
    />,
  );
}

describe("a candidate card", () => {
  it("carries the kind as text, the id, money back, the date and the rate", () => {
    const { container } = card({
      instrumentId: "UA4000239016",
      reaches: REACHES,
      span: range("2026-09-01", "2026-10-04"),
    });
    const text = container.textContent ?? "";
    expect(text).toContain("bond");
    expect(text).toContain("payments enumerated");
    expect(text).toContain("UA4000239016");
    expect(text).toContain(rendered(REACHES));
    expect(text).toContain(day("2026-10-04"));
    expect(text).toContain(rate({ tag: "rates.NominalRate", value: 0.18112850290026622 }));
  });

  it("marks every figure whose provenance marks it", () => {
    const { container } = card({ instrumentId: "A", reaches: REACHES });
    expect(container.querySelectorAll("[data-figure='marked']").length).toBeGreaterThan(1);
    expect(container.textContent).toContain("unverified");
  });

  it("renders a refused rate as the typed refusal, and keeps the card", () => {
    const { container } = card({
      instrumentId: "A",
      rate: {
        tag: "tuple.RateNotComparable",
        missing: "the span is zero days",
        reason: "an annualised rate over no time is not a rate.",
      },
    });
    const refused = container.querySelector("[data-figure='refused']");
    expect(refused?.textContent).toContain("tuple.RateNotComparable");
    expect(refused?.textContent).toContain("the span is zero days");
    expect(container.querySelector("[data-candidate='A']")).not.toBeNull();
  });

  it("carries exactly one separating badge, and the badge says which condition", () => {
    const sold = card({ instrumentId: "A", soldEarly: SOLD_EARLY });
    expect(sold.container.querySelectorAll("[data-separating]")).toHaveLength(1);
    expect(sold.container.querySelector("[data-separating]")?.textContent).toContain("sold at");

    const closed = card({ instrumentId: "B" });
    expect(closed.container.querySelector("[data-separating]")?.textContent).toContain(
      "its own terms closed it",
    );
  });

  it("names its indistinguishable neighbours rather than reading as an ordering", () => {
    const { container } = card(
      { instrumentId: "A" },
      {
        indistinguishable: {
          tag: "dominance.Indistinguishable",
          key: tuple("A"),
          neighbours: [tuple("B"), tuple("C")],
        },
      },
    );
    const line = container.querySelector("[data-indistinguishable]");
    expect(line?.textContent).toContain("B, C");
    expect(line?.textContent).toContain("not a ranking");
  });

  it("marks the belief it leans on rather than copying its statement", () => {
    const { container } = card({ instrumentId: "A", quotation: SOLD_EARLY.assumption });
    const mark = container.querySelector(`[data-belief-mark='${SOLD_EARLY.assumption.id}']`);
    expect(mark).not.toBeNull();
    expect(container.textContent).not.toContain(SOLD_EARLY.assumption.rationale);
  });

  it("shows only what this member rests on beyond the shared set", () => {
    const { container } = card(
      { instrumentId: "A", restsOn: ["everyone rests on this", "only this one does"] },
      { shared: ["everyone rests on this"] },
    );
    const own = container.querySelector("[data-disclosure='own-assumptions']");
    expect(own?.textContent).toContain("only this one does");
    expect(own?.textContent).not.toContain("everyone rests on this");
  });

  it("says the kind is unread rather than drawing nothing when the read did not answer", () => {
    const { container } = render(
      <CandidateCard
        outcome={outcome({ instrumentId: "A" })}
        reading={{ tag: "not-read", why: "the instruments read answered a refusal" }}
        shared={[]}
        indistinguishable={undefined}
      />,
    );
    expect(container.querySelector("[data-kind-state='not-read']")?.textContent).toContain(
      "kind unread",
    );
  });

  it("states the span as the two dates the API sent, and composes no length from them", () => {
    // A length is a figure the API does not send (FR-008), and FR-009's permitted lookups do
    // not cover subtracting one served date from another. OB-16 is what would put it here.
    const { container } = card({ instrumentId: "A", span: range("2026-09-01", "2026-10-04") });
    const held = container.querySelector("[data-span]");
    expect(held?.textContent).toContain(day("2026-09-01"));
    expect(held?.textContent).toContain(day("2026-10-04"));
    expect(held?.textContent).not.toMatch(/\bdays\b/);
    expect(held?.textContent).not.toContain("33");
  });

  it("passes a span date it cannot read through unchanged, never as a plausible day", () => {
    const { container } = card({ instrumentId: "A", span: range("not a date", "2026-10-04") });
    expect(container.querySelector("[data-span]")?.textContent).toContain("not a date");
  });

  it("lets no unrounded float reach the output", () => {
    const { container } = card({ instrumentId: "A", reaches: REACHES });
    const text = container.textContent ?? "";
    expect(text).toContain(`50${GROUP}529.09`);
    expect(text).not.toMatch(/\d\.\d{3,}/);
    expect(text).not.toMatch(/\de[+-]\d/);
  });
});
