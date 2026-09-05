import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { source, staleSource } from "../fixtures";

/** FR-008's five placeholders: none of them may stand where a refusal belongs. */
const PLACEHOLDERS = ["", "0", "—", "n/a", "N/A"];

describe("FigureSlot", () => {
  it("renders a value", () => {
    render(<FigureSlot state={{ kind: "value", figure: "1000 UAH" }} />);
    expect(screen.getByText("1000 UAH")).toBeInTheDocument();
  });

  it("renders a marked value with its mark as text", () => {
    render(
      <FigureSlot
        state={{
          kind: "marked",
          figure: "1000 UAH",
          marks: [{ tag: "unverified", source: source() }],
        }}
      />,
    );
    expect(screen.getByText("1000 UAH")).toBeInTheDocument();
    expect(document.body.textContent).toContain("unverified");
  });

  it("renders a stale mark as a different claim from unverified", () => {
    render(
      <FigureSlot
        state={{
          kind: "marked",
          figure: "1000 UAH",
          marks: [{ tag: "stale", source: source({ verified_on: "2026-01-01" }), stale: staleSource() }],
        }}
      />,
    );
    const text = document.body.textContent ?? "";
    expect(text).toContain("stale");
    expect(text).not.toContain("unverified");
  });

  it("renders a refusal as its reason and as none of FR-008's placeholders", () => {
    render(
      <FigureSlot
        state={{
          kind: "refused",
          refusal: {
            tag: "envelopes.NothingDeclared",
            category: "seeds",
            reason: "nothing under seeds declares a document for this owner.",
          },
        }}
      />,
    );
    const slot = screen.getByRole("note");
    expect(slot.textContent).toContain("nothing under seeds declares a document");
    for (const placeholder of PLACEHOLDERS) {
      expect(slot.textContent?.trim()).not.toBe(placeholder);
    }
    expect(document.querySelector("[data-figure='refused']")).not.toBeNull();
    expect(document.querySelector("[data-figure='value']")).toBeNull();
  });
});
