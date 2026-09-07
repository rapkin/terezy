import type { TupleOutcome } from "@/api/shapes";
import { allMoneyBackOn } from "@/answer/all-money-back";
import { notServed } from "@/answer/missing";
import { day, money } from "@/design/format";
import { assertNever } from "@/lib/exhaustive";
import { marksOf } from "@/lib/provenance";
import { FigureSlot } from "@/components/figure/FigureSlot";
import { Disclosure } from "./Disclosure";
import { FieldMissing } from "./NamedState";

/**
 * FR-016: *money back* is **one** served figure, `reaches`, and the client neither adds to it
 * nor subtracts from it.
 *
 * Measured 2026-09-06, before the engine fix, a one-month member reached 49 760.50 ₴ against
 * 50 000 ₴ asked while reporting +10.99 %, because `reaches` was measured on what was deployed
 * and the remainder was a separate field nothing brought home. The remedy was the engine's: the
 * remainder rides the declared exit route and arrives inside `reaches`. What is left for the
 * card is to show the served record beside the figure and to say, in the engine's own verdict,
 * whether the remainder came home — computing the deployed part here would be `reaches` less
 * the remainder, a figure the API does not send.
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
      <AllOfItBy outcome={outcome} />
      {remainder === null ? (
        // The ordinary whole-unit purchase. A named state and never FR-010's missing field:
        // `null` here is the API saying nothing was left over, not the API saying nothing.
        <p className="text-xs text-[var(--ink-muted)]" data-remainder="none">
          nothing left over
        </p>
      ) : (
        <Disclosure name="remainder" summary="what the purchase could not deploy">
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
          <Journey journey={remainder.journey} staleness={outcome.staleness} />
        </Disclosure>
      )}
    </div>
  );
}

/** FR-017: the served verdict on the remainder, in both of its members. */
function Journey({
  journey,
  staleness,
}: {
  journey: NonNullable<TupleOutcome["undeployed"]>["journey"];
  staleness: TupleOutcome["staleness"];
}) {
  switch (journey.tag) {
    case "tuple.RemainderCameHome":
      return (
        <p data-journey="came-home">
          it left {day(journey.left_on)} by the declared way out and arrived{" "}
          {day(journey.arrived_on)} as{" "}
          <FigureSlot
            state={{
              kind: "marked",
              figure: money(journey.reached),
              marks: marksOf(journey.reached.provenance, staleness),
            }}
          />
          , which is inside the figure above.
        </p>
      );
    case "tuple.RemainderStayed":
      // The headline is then not the whole of what was asked, and saying nothing here is the
      // measured defect FR-016 names, back in a different place.
      return (
        <div data-journey="stayed">
          <FieldMissing
            state={notServed(
              "a date on which all of it is back",
              `part of the outlay never came home: ${journey.reason}`,
            )}
          />
        </div>
      );
  }
  assertNever(journey);
}

/**
 * *All of it by*, in the three states the served record puts it in.
 *
 * `arrivals` is read at its last member rather than `span.end` being rendered: FR-009 permits a
 * lookup over served data, and this is the lookup the dominance pass itself makes, so the card
 * and the ordering cannot come to disagree.
 */
function AllOfItBy({ outcome }: { outcome: TupleOutcome }) {
  const back = allMoneyBackOn(outcome);
  switch (back.tag) {
    case "on":
      return (
        <p className="text-xs" data-all-money-back="on">
          <span className="text-[var(--ink-muted)]">all of it by </span>
          <FigureSlot state={{ kind: "value", figure: day(back.date) }} />
        </p>
      );
    case "not-all-of-it":
      return (
        <div className="text-xs" data-all-money-back="not-all-of-it">
          <FieldMissing
            state={notServed(
              "all of it by",
              `there is no date on which every hryvnia is back — ${back.reason}. Most of it is ` +
                `back on ${day(back.mostOfItOn)}.`,
            )}
          />
        </div>
      );
    case "nothing-arrived":
      return (
        <div className="text-xs" data-all-money-back="nothing-arrived">
          <FieldMissing
            state={notServed("all of it by", "the outcome records no arrival at all")}
          />
        </div>
      );
  }
  assertNever(back);
}
