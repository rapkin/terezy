import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { START_COMMAND } from "@/api/client";
import { AnswerUnavailable, LoadingState } from "@/answer/components/States";
import { FieldMissing, TypedState } from "@/answer/components/NamedState";
import { notServed } from "@/answer/missing";

/**
 * FR-013: the wait is named and the failure is named — neither is a spinner, and neither is an
 * empty column.
 */
describe("the answer's own states", () => {
  it("names what is being read, and why it takes a moment", () => {
    const { container } = render(<LoadingState />);
    const held = container.querySelector("[data-awaiting]");
    expect(held?.getAttribute("data-awaiting")).toBe("the answer");
    expect(held?.textContent).toContain("megabytes");
    expect(container.querySelector("[role='status']")).not.toBeNull();
  });

  it("names a failure and says how to start the API", () => {
    const { container } = render(
      <AnswerUnavailable answered={{ tag: "unreachable", detail: "connect ECONNREFUSED" }} />,
    );
    expect(container.querySelector("[data-api-error='unreachable']")).not.toBeNull();
    expect(container.textContent).toContain(START_COMMAND);
  });

  it("names the field a response did not carry, rather than leaving a blank", () => {
    const { container } = render(
      <FieldMissing state={notServed("a span range", "OB-16, against 020")} />,
    );
    const held = container.querySelector("[data-missing='a span range']");
    expect(held?.textContent).toContain("OB-16");
    expect((held?.textContent ?? "").trim()).not.toBe("");
  });

  it("renders a typed state's own fields, so no member of a union renders as nothing", () => {
    const { container } = render(
      <TypedState
        state={{ tag: "answer.NoHorizonDeclared" }}
        label="the question was not answered"
      />,
    );
    // A member with no `reason` and no fields at all still says which member it is.
    expect(container.textContent).toContain("answer.NoHorizonDeclared");
    expect((container.textContent ?? "").trim()).not.toBe("");
  });
});
