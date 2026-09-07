import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { EVERY_KIND, KINDS } from "@/design/kinds";
import { KindTile } from "@/design/KindTile";

/**
 * FR-002: hue is never the only carrier.
 *
 * Asserted by removing every style declaration from the rendered output and reading the kind out
 * of what is left — which is what a reader who cannot distinguish two hues is left with.
 */
function withoutStyle(html: string): string {
  return html.replace(/\s(?:style|class|fill|stroke)="[^"]*"/g, "");
}

describe("a kind tile", () => {
  for (const kind of EVERY_KIND) {
    it(`says "${KINDS[kind].word}" with every style declaration stripped`, () => {
      const { container } = render(<KindTile kind={kind} />);
      expect(withoutStyle(container.innerHTML)).toContain(KINDS[kind].word);
      expect(container.querySelector("svg")).not.toBeNull();
    });
  }

  it("draws a different icon and a different tint for two different kinds", () => {
    expect(KINDS.bond.tint).not.toBe(KINDS.fund.tint);
    expect(KINDS.bond.Icon).not.toBe(KINDS.fund.Icon);
  });
});
