import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { SyntheticFlag } from "@/components/record/SyntheticFlag";

describe("SyntheticFlag", () => {
  it("states the flag on the record, in text, in both directions (FR-019)", () => {
    const synthetic = render(<SyntheticFlag synthetic />);
    expect(synthetic.container.textContent).toContain("synthetic");
    synthetic.unmount();

    const real = render(<SyntheticFlag synthetic={false} />);
    expect(real.container.textContent).toContain("not synthetic");
  });
});
