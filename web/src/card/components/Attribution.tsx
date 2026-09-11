/**
 * FR-014, CL-2: the six-part attribution, **beside** the waterfall and labelled as its own
 * reading — *which term dominates*, against the waterfall's *where the money went*.
 *
 * Folded by default. 010 FR-005 exists for the first sentence this tool was built to write —
 * *most of the gap is the ramp, not the asset* — and no surface had ever shown it; the owner's
 * complaint about 021 was that it was overloaded, which the fold answers without dropping the
 * reading (conductor 2026-09-11, provisional).
 *
 * **Never summed.** The parts are in up to three currencies and two of them describe the same
 * money from two sides, so a reader who added them would double-count. There is no total here
 * and no line that could be read as one.
 */
import type { TupleOutcome } from "@/api/shapes";
import { money as rendered } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "@/answer/components/Disclosure";

export function Attribution({ outcome }: { outcome: TupleOutcome }) {
  return (
    <Disclosure
      name="attribution"
      summary="which term dominates — a different reading from the waterfall"
      count={outcome.parts.length}
    >
      <p className="text-xs text-[var(--ink-muted)]" data-attribution-warning>
        These six are an attribution and not an addition: they are in up to three currencies, and
        the instrument&apos;s exit terms and its lifecycle receipts describe the same money from
        two sides. Adding them double-counts. What adds up is on the waterfall.
      </p>
      <ul className="space-y-1" data-attribution>
        {outcome.parts.map((part) => (
          <li key={part.part} data-part={part.part} className="text-xs">
            <span className="text-[var(--ink-muted)]">{part.part.replace(/_/g, " ")}: </span>
            <FigureSlot
              state={{
                kind: "marked",
                figure: rendered(part.amount),
                marks: marksOf(part.amount.provenance),
              }}
            />
            <span className="text-[var(--ink-muted)]"> — from {part.source}</span>
          </li>
        ))}
      </ul>
    </Disclosure>
  );
}
