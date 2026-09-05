import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ParameterError } from "@/components/shell/ParameterError";
import { parseAsOf } from "@/search/params";

describe("ParameterError", () => {
  it("names the parameter and shows the value that was given (FR-020, US4 scenario 2)", () => {
    const parsed = parseAsOf("not-a-date");
    if (parsed.tag !== "invalid") throw new Error("expected an invalid parse");
    render(<ParameterError parsed={parsed} />);
    const alert = screen.getByRole("alert");
    expect(alert.textContent).toContain("as_of");
    expect(alert.textContent).toContain("not-a-date");
    expect(document.querySelector("[data-parameter-error='as_of']")).not.toBeNull();
  });
});
