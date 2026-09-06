import type { TupleOutcome } from "@/api/shapes";
import { notServed } from "@/answer/missing";
import { money } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "./Disclosure";
import { FieldMissing } from "./NamedState";

/**
 * FR-016: *money back* is **one** served figure, `reaches`, and the client neither adds to it
 * nor subtracts from it.
 *
 * Measured 2026-09-06 a one-month member reached 49 760.50 ₴ against 50 000 ₴ asked while
 * reporting +10.99 %, because `reaches` was measured on what was deployed and the remainder was
 * a separate field nothing brought home. The remedy is the engine's — the remainder rides the
 * declared exit route — and the card's job is to render what arrives and to say, beside it,
 * what the served record says about the rest. Computing the deployed part here would be
 * `reaches` less the remainder, a figure the API does not send.
 */
export function MoneyBack({ outcome }: { outcome: TupleOutcome }) {
  const remainder = outcome.undeployed;
  return (
    <div className="space-y-1" data-money-back>
      <p className="text-xs text-[var(--ink-muted)]">money back</p>
      <p className="text-base font-semibold">
        <FigureSlot
          state={{
            kind: "marked",
            figure: money(outcome.reaches),
            marks: marksOf(outcome.reaches.provenance, outcome.staleness),
          }}
        />
      </p>
      {remainder === null ? (
        // The ordinary whole-unit purchase. A named state and never FR-010's missing field:
        // `null` here is the API saying nothing was left over, not the API saying nothing.
        <p className="text-xs text-[var(--ink-muted)]" data-remainder="none">
          nothing left over
        </p>
      ) : (
        <Disclosure name="remainder" summary="what was left undeployed">
          <p data-remainder="served">
            <FigureSlot
              state={{
                kind: "marked",
                figure: money(remainder.amount),
                marks: marksOf(remainder.amount.provenance, outcome.staleness),
              }}
            />{" "}
            at <strong>{remainder.venue_id}</strong>
          </p>
          <p data-served-text="remainder-reason">{remainder.reason}</p>
          {remainder.amount.currency === outcome.reaches.currency ? null : (
            // The cross-currency case: no exchange rate is consulted anywhere on this screen, so
            // the remainder cannot join the headline and the headline must say so rather than
            // stand for the whole amount.
            <FieldMissing
              state={notServed(
                "a verdict on whether the remainder came home",
                `it is in ${remainder.amount.currency} and money back is in ` +
                  `${outcome.reaches.currency}; no rate is consulted here, so the headline is ` +
                  "not the whole of what was asked",
              )}
            />
          )}
        </Disclosure>
      )}
    </div>
  );
}
