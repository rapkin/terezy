import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { FieldRow } from "@/components/record/FieldRow";
import { RecordCard } from "@/components/record/RecordCard";
import type { StalenessVerdict } from "@/api/shapes";
import { declaration, field, instrumentRead, money, source, staleSource, verdict } from "../fixtures";

/**
 * FR-023 as a biconditional, and FR-023a beside it.
 *
 * The one-directional reading -- *`as_of` changes something* -- is satisfied by a screen that
 * re-renders on every date and says nothing true, so both halves are asserted: a move across a
 * source's threshold changes that source's staleness state, and a move crossing none changes no
 * staleness state at all. The verdict is the API's: it is what `as_of` moves, and the client
 * neither computes it nor ages anything itself.
 */
const OBSERVED = source();

function readOf(verdicted: StalenessVerdict | undefined): {
  marks: readonly string[];
  figure: string;
} {
  const view = render(
    <FieldRow field={field({ name: "face_value" })} value={money(1000, [OBSERVED])} verdict={verdicted} />,
  );
  const marks = [...view.container.querySelectorAll("[data-mark]")].map(
    (held) => held.getAttribute("data-mark") ?? "",
  );
  const figure = view.container.querySelector("[data-figure]")?.firstChild?.textContent ?? "";
  view.unmount();
  return { marks, figure };
}

const NOTHING_STALE = verdict([]);
const THIS_SOURCE_STALE = verdict([staleSource({ source_id: OBSERVED.id })]);
const ANOTHER_SOURCE_STALE = verdict([staleSource({ source_id: "cpi/ua.toml#2025-10" })]);

describe("moving as_of", () => {
  it("changes a source's staleness state when the API's verdict crosses its threshold", () => {
    expect(readOf(NOTHING_STALE).marks).not.toContain("stale");
    expect(readOf(THIS_SOURCE_STALE).marks).toContain("stale");
  });

  it("changes no staleness state when the verdict crosses none of this figure's thresholds", () => {
    expect(readOf(ANOTHER_SOURCE_STALE).marks).toEqual(readOf(NOTHING_STALE).marks);
  });

  it("leaves the figure itself untouched either way (FR-023a)", () => {
    expect(readOf(THIS_SOURCE_STALE).figure).toBe(readOf(NOTHING_STALE).figure);
  });

  it("renders a figure the API returned identically twice identically twice", () => {
    const first = render(<RecordCard read={instrumentRead({ as_of: "2026-09-05" })} />);
    const firstText = first.container.textContent ?? "";
    first.unmount();
    const second = render(<RecordCard read={instrumentRead({ as_of: "2027-09-05" })} />);
    const secondText = second.container.textContent ?? "";
    second.unmount();
    expect(secondText.replace("2027-09-05", "2026-09-05")).toBe(firstText);
  });

  it("renders a figure the API resolved differently as it arrived, suppressing nothing", () => {
    const cheap = render(<RecordCard read={instrumentRead({ result: declaration(1000) })} />);
    const cheapText = cheap.container.textContent ?? "";
    cheap.unmount();
    const dearer = render(<RecordCard read={instrumentRead({ result: declaration(2000) })} />);
    const dearerText = dearer.container.textContent ?? "";
    dearer.unmount();
    expect(dearerText).not.toBe(cheapText);
    expect(dearerText).toContain("2000 UAH");
  });
});
