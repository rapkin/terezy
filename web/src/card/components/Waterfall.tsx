/**
 * FR-013 to FR-019: where the money went, bar by bar, each one a figure the API sent.
 *
 * The bars are **readable as text with every style declaration stripped**: the amount, the label
 * and the mark are all in the document, and the coloured rule beside each is emphasis. That is
 * FR-029's requirement rather than a preference — a waterfall whose claim lives in a bar's width
 * is a waterfall a screen reader cannot read.
 */
import type { CandidateProjection, Currency, TupleOutcome } from "@/api/shapes";
import { barsOf, type Bar } from "@/card/bars";
import { currenciesOf, inCurrency, sharesOneCurrency } from "@/card/currencies";
import { currencySymbol, day, money as rendered } from "@/design/format";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { TaxBar } from "./TaxBar";

export function Waterfall({
  projection,
  outcome,
}: {
  projection: CandidateProjection;
  outcome: TupleOutcome;
}) {
  const bars = barsOf(projection, outcome);
  const joined = sharesOneCurrency(bars);
  return (
    <section className="space-y-3" data-waterfall aria-label="where the money went">
      <h3 className="text-sm font-semibold">where the money went</h3>
      <DoesNotSum />
      {joined ? (
        <BarList bars={bars} outcome={outcome} />
      ) : (
        <SplitByCurrency bars={bars} outcome={outcome} />
      )}
    </section>
  );
}

/**
 * FR-019: the bars do not add up to the ranking's rate, and the card says so rather than
 * letting a reader discover it by adding them.
 */
function DoesNotSum() {
  return (
    <p className="text-xs text-[var(--ink-muted)]" data-does-not-sum>
      These bars do not add up to the rate this candidate is ranked by, and they are not meant to:
      the rate is measured over the span the money was actually out, the horizon is the window, and
      three terms sit outside the addition — the tax is netted before a percentage exit fee, a date
      whose payment its own tax consumed exactly leaves the release series, and the purchase is
      accounted for on the way in.
    </p>
  );
}

/** FR-015: where the bars are not all in one currency there is no connected waterfall. */
function SplitByCurrency({ bars, outcome }: { bars: readonly Bar[]; outcome: TupleOutcome }) {
  return (
    <div className="space-y-3" data-currencies-split>
      <p className="text-xs" role="note" data-split-reason>
        These bars are in more than one currency, so they are grouped rather than joined: no
        baseline runs through them and no rate is consulted. The display-currency switch is
        deferred, and every declared channel&apos;s reference rate is a fixture.
      </p>
      {currenciesOf(bars).map((currency: Currency) => (
        <div key={currency} data-currency-group={currency}>
          <p className="text-xs font-semibold">{currencySymbol(currency)}</p>
          <BarList bars={inCurrency(bars, currency)} outcome={outcome} />
        </div>
      ))}
    </div>
  );
}

function BarList({ bars, outcome }: { bars: readonly Bar[]; outcome: TupleOutcome }) {
  return (
    <ol className="space-y-2">
      {bars.map((bar) => (
        <li key={bar.id} data-bar={bar.id} data-bar-kind={bar.kind}>
          <BarRow bar={bar} outcome={outcome} />
        </li>
      ))}
    </ol>
  );
}

function BarRow({ bar, outcome }: { bar: Bar; outcome: TupleOutcome }) {
  switch (bar.tag) {
    case "tax":
      return (
        <>
          <Label bar={bar} />
          <TaxBar amount={bar.amount} base={bar.base} taxClassId={bar.taxClassId} on={bar.on} />
        </>
      );
    case "none":
      return (
        <>
          <Label bar={bar} />
          <p className="text-xs text-[var(--ink-muted)]" data-bar-none={bar.id}>
            {bar.reason}
          </p>
        </>
      );
    case "refused":
      // FR-016: an absence is not a zero, and it is drawn as its own state carrying the reason.
      return (
        <>
          <Label bar={bar} />
          <FigureSlot
            state={{
              kind: "refused-in-answer",
              tag: bar.state.tag,
              reason: bar.state.reason,
              detail: (
                <p className="mt-1 text-xs">
                  what is missing: {bar.state.what}, on the {bar.state.arm} arm
                </p>
              ),
            }}
          />
        </>
      );
    case "amount":
      return (
        <>
          <Label bar={bar} />
          <p className="text-sm">
            <FigureSlot
              state={{
                kind: "marked",
                figure: rendered(bar.amount),
                // FR-018: the bar's **own** mark. An amount the API sent unmarked wears its
                // outcome's instead, and the line beside it says whose.
                marks: bar.amount.provenance.sources.length
                  ? marksOf(bar.amount.provenance)
                  : marksOf(outcome.provenance, outcome.staleness),
              }}
            />
            {bar.amount.provenance.sources.length === 0 ? (
              <span className="text-[var(--ink-muted)]" data-mark-owner="outcome">
                {" "}
                (this amount cites nothing of its own; the marks are the outcome&apos;s)
              </span>
            ) : null}
          </p>
        </>
      );
  }
}

function Label({ bar }: { bar: Bar }) {
  const on = bar.tag === "refused" || bar.tag === "none" ? null : bar.on;
  return (
    <p className="text-xs text-[var(--ink-muted)]">
      {bar.label}
      {on === null ? null : ` — ${day(on)}`}
    </p>
  );
}
