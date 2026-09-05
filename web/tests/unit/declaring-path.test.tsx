import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { DeclaringPath } from "@/components/record/DeclaringPath";

describe("DeclaringPath", () => {
  it("shows the path of the declaring file as text (FR-018)", () => {
    render(<DeclaringPath declaredIn="instruments/UA4000207518.toml" />);
    expect(screen.getByText(/instruments\/UA4000207518\.toml/)).toBeInTheDocument();
  });

  it("shows the API's refusal where the file was not recorded", () => {
    render(
      <DeclaringPath
        declaredIn={{
          tag: "envelopes.FileNotRecorded",
          category: "access",
          reason: "this category's resolver returns no file map.",
        }}
      />,
    );
    expect(screen.getByRole("note").textContent).toContain("returns no file map");
  });

  it("says so where the API sent none, rather than leaving the slot blank", () => {
    const { container } = render(<DeclaringPath declaredIn={null} />);
    expect(container.textContent).toContain("no file recorded");
  });
});
