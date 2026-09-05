import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { Provenance } from "@/components/figure/Provenance";
import { marksOf } from "@/lib/provenance";
import { provenance, source, staleSource, verdict } from "../fixtures";

describe("Provenance", () => {
  it("renders citation, retrieved_on and verified_on for every source (FR-017, SC-004)", () => {
    const { container } = render(
      <Provenance provenance={provenance([source({ verified_on: "2026-09-01" })])} />,
    );
    const text = container.textContent ?? "";
    expect(text).toContain("bank.gov.ua/depo_securities");
    expect(text).toContain("retrieved_on 2026-08-31");
    expect(text).toContain("verified_on 2026-09-01");
  });

  it("renders an empty verified_on as the unverified mark and never as an empty field", () => {
    const { container } = render(<Provenance provenance={provenance([source()])} />);
    const text = container.textContent ?? "";
    expect(text).toContain("verified_on not recorded");
    expect(text).toContain("unverified");
  });

  it("keeps unverified and stale apart: neither implies the other (FR-012)", () => {
    const verified = source({ verified_on: "2026-01-01" });
    const stale = marksOf(provenance([verified]), verdict([staleSource({ source_id: verified.id })]));
    expect(stale.map((mark) => mark.tag)).toEqual(["stale"]);

    const unverified = marksOf(provenance([source()]), verdict([]));
    expect(unverified.map((mark) => mark.tag)).toEqual(["unverified"]);
  });

  it("reads is_unverified off the response rather than recomputing it (020 FR-018)", () => {
    const stated = { ...provenance([source({ verified_on: "2026-01-01" })]), is_unverified: true };
    const { container } = render(<Provenance provenance={stated} />);
    expect(container.querySelector("[data-provenance='unverified']")).not.toBeNull();
  });
});
