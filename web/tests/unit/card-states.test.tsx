import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { TypedState } from "@/answer/components/NamedState";
import { remedyFor } from "@/card/refusals";
import { ApiErrorState } from "@/components/shell/ApiErrorState";
import { START_COMMAND } from "@/api/client";

/**
 * SC-006: the card's failures are named states, never an empty card — a card that failed to load
 * and a candidate with nothing to show look the same.
 *
 * The **wait** is 021's `Awaiting`, rendered by the route with what it is reading; that component
 * is tested where it lives, and `e2e/card-text.spec.ts` asserts the route names it.
 */
describe("the card's own states", () => {
  it("names an unreachable API rather than an empty card", () => {
    const { container } = render(
      <ApiErrorState
        answered={{ tag: "unreachable", detail: "connect ECONNREFUSED" }}
        what="this candidate's flows"
      />,
    );
    expect(container.querySelector("[data-api-error='unreachable']")).not.toBeNull();
    expect(container.textContent).toContain(START_COMMAND);
  });

  it("renders a key from another answer as its own state, with its own remedy", () => {
    const refusal = {
      tag: "card.NoSuchCandidate" as const,
      wanted_key: "2026-01-01..2026-02-01|X|salary_uah",
      evaluated_keys: ["a", "b"],
      reason: "no candidate of this answer is addressed by that key",
    };
    const { container } = render(
      <TypedState state={{ ...refusal, remedy: remedyFor(refusal) }} label="this candidate has no card" />,
    );
    expect(container.querySelector("[data-typed-state='card.NoSuchCandidate']")).not.toBeNull();
    expect(container.textContent).toContain("reopen the answer");
    expect((container.textContent ?? "").trim()).not.toBe("");
  });

  it("renders an undeclared question as a different state, with a different remedy", () => {
    const refusal = {
      tag: "envelopes.CategoryHasNoSuchId" as const,
      category: "questions",
      wanted_id: "nope",
      declared_ids: ["fifty-thousand-hryvnia"],
      reason: "no question with that id is declared",
    };
    const { container } = render(
      <TypedState state={{ ...refusal, remedy: remedyFor(refusal) }} label="this candidate has no card" />,
    );
    expect(container.querySelector("[data-typed-state='envelopes.CategoryHasNoSuchId']")).not.toBeNull();
    expect(container.textContent).toContain("open one of the declared ones");
  });
});
