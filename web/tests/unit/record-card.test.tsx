import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RecordCard } from "@/components/record/RecordCard";
import { field, instrumentRead } from "../fixtures";

describe("RecordCard", () => {
  it("shows every field the API returns, in the order returned (FR-016)", () => {
    const read = instrumentRead();
    const { container } = render(<RecordCard read={read} />);
    const rendered = [...container.querySelectorAll("[data-field]")].map((held) =>
      held.getAttribute("data-field"),
    );
    expect(rendered).toEqual(read.fields.map((held) => held.name));
  });

  it("shows a field it has no special rendering for with its raw value (US1 scenario 4)", () => {
    const read = instrumentRead();
    render(
      <RecordCard
        read={{
          ...read,
          fields: [...read.fields, field({ name: "instrument_class" })],
        }}
      />,
    );
    expect(screen.getByText("enumerated_schedule")).toBeInTheDocument();
  });

  it("marks each figure rather than replacing them with one banner (FR-011)", () => {
    render(<RecordCard read={instrumentRead()} />);
    const marked = document.querySelectorAll("[data-figure='marked']");
    expect(marked.length).toBeGreaterThanOrEqual(2);
    expect(document.querySelectorAll("[data-mark='unverified']").length).toBeGreaterThanOrEqual(2);
  });

  it("renders a refused result as the refusal, never as an empty card", () => {
    const read = instrumentRead();
    render(
      <RecordCard
        read={{
          ...read,
          result: {
            tag: "envelopes.CategoryHasNoSuchId",
            category: "instruments",
            wanted_id: "UA999",
            declared_ids: ["UA1"],
            reason: "the category 'instruments' declares no 'UA999'.",
          },
        }}
      />,
    );
    expect(screen.getByRole("note").textContent).toContain("declares no 'UA999'");
    expect(document.querySelectorAll("[data-field]")).toHaveLength(0);
  });

  it("renders the declaring file path and the synthetic flag on the card", () => {
    render(<RecordCard read={instrumentRead()} />);
    expect(document.body.textContent).toContain("declared in: instruments/UA1.toml");
    expect(document.querySelector("[data-synthetic='false']")).not.toBeNull();
  });

  it("renders a citation exemption with its reason instead of an empty citation block", () => {
    render(
      <RecordCard
        read={instrumentRead()}
        policy={{
          tag: "citation_policy.CitationsExempt",
          path: "goals",
          reason: "this directory holds the owner's own statements, not observations.",
        }}
      />,
    );
    const note = document.querySelector("[data-citations='exempt']");
    expect(note?.textContent).toContain("the owner's own statements");
  });
});
