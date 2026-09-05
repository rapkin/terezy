import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { FieldRow } from "@/components/record/FieldRow";
import { field, money, source, staleSource, verdict } from "../fixtures";

describe("FieldRow", () => {
  it("shows the label, the type and the value", () => {
    render(<FieldRow field={field({ name: "instrument_class" })} value="enumerated_schedule" />);
    expect(screen.getByText("instrument_class")).toBeInTheDocument();
    expect(screen.getByText("enumerated_schedule")).toBeInTheDocument();
  });

  it("uses the API's own field name as the label, untranslated", () => {
    render(<FieldRow field={field({ name: "verified_on" })} value="2026-01-01" />);
    expect(screen.getByText("verified_on")).toBeInTheDocument();
  });

  it("renders an observed value marked, with its citation and both dates (FR-017, SC-004)", () => {
    const cited = source();
    const { container } = render(
      <FieldRow field={field({ name: "face_value" })} value={money(1000, [cited])} />,
    );
    expect(container.querySelector("[data-figure='marked']")).not.toBeNull();
    expect(container.textContent).toContain("1000 UAH");
    expect(container.querySelector(`[data-citation="${cited.id}"]`)?.textContent).toBe(
      cited.citation,
    );
    expect(container.textContent).toContain(`retrieved_on ${cited.retrieved_on}`);
    expect(container.textContent).toContain("verified_on not recorded");
    expect(container.textContent).toContain("unverified");
  });

  it("renders a verified amount's citation and its verification date, unmarked", () => {
    const checked = source({ verified_on: "2026-09-01" });
    const { container } = render(
      <FieldRow field={field({ name: "face_value" })} value={money(1000, [checked])} />,
    );
    expect(container.querySelector("[data-figure='value']")).not.toBeNull();
    expect(container.querySelector(`[data-citation="${checked.id}"]`)?.textContent).toBe(
      checked.citation,
    );
    expect(container.textContent).toContain("verified_on 2026-09-01");
  });

  it("renders an unmarked value without inventing a mark", () => {
    const { container } = render(
      <FieldRow
        field={field({ name: "face_value" })}
        value={money(1000, [source({ verified_on: "2026-01-01" })])}
      />,
    );
    expect(container.querySelector("[data-figure='value']")).not.toBeNull();
    expect(container.querySelector("[data-figure='marked']")).toBeNull();
    expect(container.querySelector("[data-mark]")).toBeNull();
  });

  it("renders a refused value as the refusal (FR-007's third state)", () => {
    render(
      <FieldRow
        field={field({ name: "amount" })}
        value={{
          tag: "envelopes.NothingDeclared",
          category: "spendable",
          reason: "nothing under spendable declares a document for this owner.",
        }}
      />,
    );
    expect(screen.getByRole("note").textContent).toContain("nothing under spendable declares");
  });

  it("shows an absent field as declared-absent, never as a blank cell", () => {
    // Both spellings: a declared `null` and a key the body omitted, which arrives as `undefined`.
    for (const absent of [null, undefined]) {
      const view = render(
        <FieldRow field={field({ name: "rule", optional: true })} value={absent} />,
      );
      expect(view.container.querySelector("[data-value='absent']")?.textContent).toBe(
        "not declared",
      );
      view.unmount();
    }
  });

  it("carries the stale mark where the response's verdict names the source (FR-012)", () => {
    const verified = source({ verified_on: "2026-01-01" });
    render(
      <FieldRow
        field={field({ name: "face_value" })}
        value={money(1000, [verified])}
        verdict={verdict([staleSource({ source_id: verified.id })])}
      />,
    );
    expect(document.querySelector("[data-mark='stale']")).not.toBeNull();
    expect(document.querySelector("[data-mark='unverified']")).toBeNull();
  });
});
