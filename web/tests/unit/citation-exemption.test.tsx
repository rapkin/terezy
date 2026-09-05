import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CitationPolicyNote } from "@/components/figure/CitationExemption";

describe("CitationPolicyNote", () => {
  it("renders an exemption with the API's reason, never an empty citation block (FR-013)", () => {
    const { container } = render(
      <CitationPolicyNote
        policy={{
          tag: "citation_policy.CitationsExempt",
          path: "goals",
          reason: "this directory holds the owner's own statements, not observations.",
        }}
      />,
    );
    expect(container.textContent).toContain("citations exempt for goals");
    expect(container.textContent).toContain("the owner's own statements");
    expect(container.textContent?.trim()).not.toBe("");
  });

  it("says a directory requires citations where it does", () => {
    const { container } = render(
      <CitationPolicyNote
        policy={{ tag: "citation_policy.CitationsRequired", path: "instruments" }}
      />,
    );
    expect(container.textContent).toContain("citations required for instruments");
  });
});
