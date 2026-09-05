import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { LongValue } from "@/components/record/LongValue";

describe("LongValue", () => {
  it("shows a multi-sentence citation in full, with no elision", () => {
    const citation =
      "INFERENCE: nothing below is inferred, and the marker is required anyway. " +
      "Transcribed verbatim from https://bank.gov.ua/depo_securities?json — the National Bank " +
      "of Ukraine's depository register of government securities, retrieved 2026-08-31. " +
      "Reused under ст. 10¹ ч. 2 Закону України «Про доступ до публічної інформації».";
    const { container } = render(<LongValue text={citation} />);
    expect(container.textContent).toBe(citation);
    expect(container.textContent).not.toContain("…");
    expect(container.textContent).not.toContain("...");
  });
});
