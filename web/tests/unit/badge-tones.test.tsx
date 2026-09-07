import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Badge } from "@/components/ui/badge";

/**
 * FR-003: four tones, and `assume` is one of them rather than a restyled `warn`.
 *
 * The two say different things — `warn` is a claim about a figure's source, `assume` a claim
 * about what a candidate rests on — so the assertion is that they do not resolve to the same
 * tokens, which is what a copy of `warn` under a new name would do.
 */
const TONES = ["neutral", "warn", "refuse", "assume"] as const;

describe("the badge tones", () => {
  for (const tone of TONES) {
    it(`${tone} renders its own text`, () => {
      const { container } = render(<Badge tone={tone}>{`this is ${tone}`}</Badge>);
      expect(container.textContent).toBe(`this is ${tone}`);
    });
  }

  it("gives assume its own tokens rather than warn's", () => {
    const classesFor = (tone: (typeof TONES)[number]) => {
      const { container } = render(<Badge tone={tone}>x</Badge>);
      return container.firstElementChild?.getAttribute("class") ?? "";
    };
    const assume = classesFor("assume");
    expect(assume).toContain("--assume-ink");
    expect(assume).not.toContain("--warn-ink");
    expect(new Set(TONES.map(classesFor)).size).toBe(TONES.length);
  });
});
