import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Mark } from "@/components/figure/Mark";
import { source, staleSource } from "../fixtures";

/**
 * FR-009: the assertion strips every style declaration first and then reads the mark -- the
 * reading `tests/contract/test_diagram_marks.py` already applies to diagrams, carried onto a
 * rendered page. A mark carried by colour alone survives the first read and not this one.
 */
function textWithoutStyling(root: HTMLElement): string {
  const stripped = root.cloneNode(true);
  if (!(stripped instanceof HTMLElement)) throw new Error("clone lost its element");
  for (const element of [stripped, ...stripped.querySelectorAll("*")]) {
    if (element instanceof HTMLElement) {
      element.removeAttribute("style");
      element.removeAttribute("class");
    }
  }
  for (const sheet of document.querySelectorAll("style, link[rel='stylesheet']")) sheet.remove();
  return stripped.textContent ?? "";
}

describe("Mark", () => {
  it("carries the unverified claim in text once every style declaration is stripped", () => {
    const { container } = render(<Mark mark={{ tag: "unverified", source: source() }} />);
    const text = textWithoutStyling(container);
    expect(text).toContain("unverified");
    expect(text).toContain("instruments/UA1.toml#terms");
    expect(text).toContain("2026-08-31");
  });

  it("carries the stale claim in text, with the threshold it is measured against", () => {
    const { container } = render(
      <Mark mark={{ tag: "stale", source: source(), stale: staleSource() }} />,
    );
    const text = textWithoutStyling(container);
    expect(text).toContain("stale");
    expect(text).toContain("30-day threshold");
    expect(text).toContain("70 days");
  });
});
