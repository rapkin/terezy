/**
 * FR-017 and required test **E11**: a tax bar that says which zero it is.
 *
 * The base sits beside the charge and the class is named, because a charge with neither is a
 * figure a reader cannot check. No **rate** is shown: the engine records none, and reading the
 * declared class to render its dated rates would be this client deciding which entry applied on
 * the event's date (CL-1, conductor 2026-09-11, provisional).
 */
import type { Money } from "@/api/shapes";
import { day, money as rendered } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { Badge } from "@/components/ui/badge";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { taxZero } from "@/card/zeros";

export function TaxBar({
  amount,
  base,
  taxClassId,
  on,
}: {
  amount: Money;
  base: Money | null;
  taxClassId: string | null;
  on: string | null;
}) {
  const zero = taxZero(amount);
  return (
    <div className="space-y-1" data-tax-zero={zero.tag}>
      <p className="text-xs">
        {/* A zero no rule ran on cites nothing, so there is no mark for it to wear and none is
            invented. What says so is the badge below, which is the stronger statement. */}
        <FigureSlot
          state={
            zero.tag === "no-rule-ran"
              ? { kind: "value", figure: rendered(amount) }
              : { kind: "marked", figure: rendered(amount), marks: marksOf(amount.provenance) }
          }
        />
        {base === null || taxClassId === null ? null : (
          <>
            <span className="text-[var(--ink-muted)]"> struck on </span>
            <FigureSlot
              state={{ kind: "marked", figure: rendered(base), marks: marksOf(base.provenance) }}
            />
            <span className="text-[var(--ink-muted)]"> by </span>
            <span className="font-mono" data-tax-class={taxClassId}>
              {taxClassId}
            </span>
          </>
        )}
        {on === null ? null : (
          <span className="text-[var(--ink-muted)]"> on {day(on)}</span>
        )}
      </p>
      <WhichZero zero={zero} />
    </div>
  );
}

/** The two zeros, in words, and never the same words. */
function WhichZero({ zero }: { zero: ReturnType<typeof taxZero> }) {
  switch (zero.tag) {
    case "charged":
      return null;
    case "exempted":
      return (
        <Badge tone="neutral" data-zero="exempted">
          nothing was charged, and the exemption is cited:{" "}
          {zero.sources.map((source) => source.id).join(", ")}
        </Badge>
      );
    case "no-rule-ran":
      return (
        <Badge tone="warn" data-zero="no-rule-ran">
          no tax rule ran on this line, so its zero rests on no source — which is a different
          claim from an exemption
        </Badge>
      );
  }
}
