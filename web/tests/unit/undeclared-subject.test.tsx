import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { AnswerHeader } from "@/answer/components/AnswerHeader";
import { remedyFor } from "@/answer/remedies";
import { GROUP } from "@/design/format";
import { answer } from "../answer-fixtures";

/**
 * FR-021: a subject the registry declares nothing by is a refusal carrying its remedy and the
 * feature that supplies it — never blank space.
 *
 * FR-011: **every** amount, with the stream it leaves. Measured 2026-09-06 there are two, and
 * the second is the stream every folded no-candidate refusal names — so a header showing one
 * amount hides the reason for the largest refusal group on the screen.
 */
function header(subjects: Parameters<typeof answerWith>[0]) {
  return render(<AnswerHeader answer={answerWith(subjects)} />);
}

function answerWith(subjects: Parameters<typeof AnswerHeader>[0]["answer"]["subjects"]) {
  return answer({ subjects });
}

const UNDECLARED = { tag: "answer.UndeclaredSubject" as const, named: "btc" };

describe("the answer header", () => {
  it("states every amount the question carries, with the stream it leaves", () => {
    const { container } = header([]);
    const text = container.textContent ?? "";
    expect(text).toContain(`50${GROUP}000.00${GROUP}₴`);
    expect(text).toContain("salary_uah");
    expect(text).toContain(`1.00${GROUP}$`);
    expect(text).toContain("contract_usd");
  });

  it("names the benchmark instrument and the date it was answered as of", () => {
    const { container } = header([]);
    expect(container.textContent).toContain("UA4000231195");
    expect(container.textContent).toContain("5 Sep 2026");
  });

  it("asserts no standing, because a standing is per section", () => {
    const { container } = header([]);
    expect(container.textContent).not.toContain("dominat");
  });

  it("renders an undeclared subject as a refusal with its remedy, never blank", () => {
    const { container } = header([UNDECLARED]);
    const refusal = container.querySelector("[data-undeclared-subject='btc']");
    expect(refusal?.textContent).toContain("a declaration");
    expect(refusal?.querySelector("[data-remedy-feature]")).not.toBeNull();
    expect((refusal?.textContent ?? "").trim()).not.toBe("");
  });

  it("states the remedy for a subject no feature is recorded against", () => {
    // Measured 2026-09-07: 023 and 025 landed, so the shipped answer reports no undeclared
    // subject at all and the feature map is empty. The remedy itself is not.
    expect(remedyFor("btc").remedy).toBe("a declaration");
    expect(remedyFor("btc").suppliedBy).toBeNull();
  });

  it("says so plainly where the question names no subject, rather than an empty list", () => {
    const { container } = header([]);
    expect(container.querySelector("[data-subjects='none']")?.textContent).toContain(
      "names no subject",
    );
    expect(container.querySelector("ul[data-subjects]")).toBeNull();
  });

  it("still states the remedy for a subject the map has no feature for", () => {
    const { container } = header([{ tag: "answer.UndeclaredSubject", named: "gold" }]);
    const refusal = container.querySelector("[data-undeclared-subject='gold']");
    expect(refusal?.textContent).toContain("a declaration");
    expect(refusal?.querySelector("[data-remedy-feature='unrecorded']")).not.toBeNull();
    expect((refusal?.textContent ?? "").trim()).not.toBe("");
  });

  it("states a declared subject's count rather than dropping it", () => {
    const { container } = header([
      { tag: "answer.DeclaredSubject", named: "ovdp", is_group: true, ids: ["A", "B"] },
    ]);
    expect(container.querySelector("[data-subject='ovdp']")?.textContent).toContain("2 declared");
  });
});
