import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { CategoryIndex } from "@/components/category/CategoryIndex";
import { RecordList } from "@/components/category/RecordList";
import { EmptyCategory } from "@/components/category/EmptyCategory";
import { renderInRouter } from "../router";
import { keyedSummary, registry, singletonSummary } from "../fixtures";

describe("CategoryIndex", () => {
  it("lists exactly the categories the API sent, and no other", async () => {
    const { container } = await renderInRouter(
      <CategoryIndex registry={registry([keyedSummary(), singletonSummary()])} />,
    );
    const shapes = [...container.querySelectorAll("[data-shape]")];
    expect(shapes).toHaveLength(2);
    expect(container.textContent).toContain("instruments");
    expect(container.textContent).toContain("seeds");
  });

  it("renders a keyed category as a count and a singleton as whether it resolved (FR-014)", async () => {
    const { container } = await renderInRouter(
      <CategoryIndex registry={registry([keyedSummary(), singletonSummary()])} />,
    );
    const keyed = container.querySelector("[data-shape='keyed']");
    const singleton = container.querySelector("[data-shape='singleton']");
    expect(keyed?.textContent).toContain("26 declared");
    expect(singleton?.textContent).toContain("resolved");
    expect(singleton?.textContent).not.toContain("0");
  });

  it("renders an unresolved singleton as unresolved and never as a count of zero", async () => {
    const { container } = await renderInRouter(
      <CategoryIndex registry={registry([singletonSummary({ resolved: false })])} />,
    );
    const singleton = container.querySelector("[data-shape='singleton']");
    expect(singleton?.textContent).toContain("not resolved");
    expect(singleton?.textContent).not.toContain("0");
  });

  it("renders the citation exemption on the card that carries one", async () => {
    const { container } = await renderInRouter(<CategoryIndex registry={registry([singletonSummary()])} />);
    expect(container.querySelector("[data-citations='exempt']")?.textContent).toContain(
      "the owner's own statements",
    );
  });
});

describe("RecordList", () => {
  it("lists the ids the API returned, in the order returned (FR-002)", async () => {
    const { container } = await renderInRouter(
      <RecordList
        listing={{
          tag: "envelopes.ListingOfInstruments",
          category: "instruments",
          as_of: "2026-09-05",
          scenario_id: null,
          ids: ["UA2", "UA1"],
        }}
      />,
    );
    const links = [...container.querySelectorAll("li a")].map((held) => held.textContent);
    expect(links).toEqual(["UA2", "UA1"]);
  });

  it("renders an empty category and an absent one differently (*Edge Cases*)", async () => {
    const empty = await renderInRouter(
      <RecordList
        listing={{
          tag: "envelopes.ListingOfInstruments",
          category: "instruments",
          as_of: "2026-09-05",
          scenario_id: null,
          ids: [],
        }}
      />,
    );
    expect(empty.container.querySelector("[data-records='0']")?.textContent).toContain(
      "is declared and holds no record",
    );
    empty.unmount();

    const absent = render(<EmptyCategory category="instruments" />);
    expect(absent.container.textContent).not.toBe("");
  });
});
