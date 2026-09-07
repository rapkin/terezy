import type { HeldPosition } from "@/api/shapes";
import { money, quantity } from "@/design/format";
import { KindTile } from "@/design/KindTile";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "./Disclosure";
import { TypedState } from "./NamedState";
import { Population } from "./Population";

/**
 * What the owner already holds, beside what he could do with the amount he asked about.
 *
 * A held position is not a candidate — 025 declares it `NotRankedAgainstTheBenchmark`, because
 * the question is what to do with money he has not spent — so it is drawn as its own block and
 * never as a card on a front. Every verdict it carries is typed, including the one that matters
 * most: a valuation the registry cannot strike is a refusal with its reason and never a blank
 * where a number should be.
 */
export function HeldPositions({
  held,
  staleness,
}: {
  held: readonly HeldPosition[];
  staleness: Parameters<typeof marksOf>[1];
}) {
  return (
    <Population
      name="what the owner already holds"
      members={held}
      render={(position) => <Held position={position} staleness={staleness} />}
    />
  );
}

function Held({
  position,
  staleness,
}: {
  position: HeldPosition;
  staleness: Parameters<typeof marksOf>[1];
}) {
  return (
    <div className="space-y-1" data-held={position.instrument_id}>
      <p className="flex flex-wrap items-center gap-2">
        <KindTile kind="held_asset" size="inline" />
        <span className="font-mono">{position.instrument_id}</span>
        <span className="text-[var(--ink-muted)]">
          {quantity(position.quantity)} {position.quantity_unit} at {position.venue_id}
        </span>
      </p>
      <p>
        <span className="text-[var(--ink-muted)]">what it cost </span>
        <FigureSlot
          state={{
            kind: "marked",
            figure: money(position.basis),
            marks: marksOf(position.basis.provenance, staleness),
          }}
        />
      </p>
      <div>
        <span className="text-[var(--ink-muted)]">what it is worth </span>
        <Worth valuation={position.valuation} staleness={staleness} />
      </div>
      <Disclosure name="held-verdicts" summary="what else the registry says about it">
        <TypedState state={position.rank} label="against the benchmark" />
        <TypedState state={position.tax} label="tax" />
        <TypedState state={position.yields} label="yield" />
        <Population
          name="lots"
          members={position.lots}
          render={(lot) => (
            <p data-lot={lot.lot_id}>
              {quantity(lot.quantity)} acquired {lot.acquired_on} for{" "}
              <FigureSlot
                state={{
                  kind: "marked",
                  figure: money(lot.basis),
                  marks: marksOf(lot.basis.provenance, staleness),
                }}
              />
            </p>
          )}
        />
      </Disclosure>
    </div>
  );
}

/** FR-010: a valuation the registry could not strike is its own reason, never an empty slot. */
function Worth({
  valuation,
  staleness,
}: {
  valuation: HeldPosition["valuation"];
  staleness: Parameters<typeof marksOf>[1];
}) {
  if (valuation.tag !== "held.Valued") {
    return (
      <FigureSlot
        state={{ kind: "refused-in-answer", tag: valuation.tag, reason: valuation.reason }}
      />
    );
  }
  return (
    <FigureSlot
      state={{
        kind: "marked",
        figure: money(valuation.value),
        marks: marksOf(valuation.value.provenance, staleness),
      }}
    />
  );
}
