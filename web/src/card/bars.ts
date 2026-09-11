/**
 * FR-013: the waterfall's bars, in the order the money moved, each one a **served** figure.
 *
 * Nothing here subtracts one served amount from another. Every bar's amount is a field the API
 * sent: the way in's charge is its components, the exit's is the per-release components, and
 * what reached home is `reaches` rather than the sum of what is above it. `bars.test.ts` has one
 * case per row of the plan's mapping table, and `no-derived-bar.test.ts` scans this tree for the
 * arithmetic the rule forbids.
 *
 * **Not built from `TupleOutcome.parts`.** Those six are an attribution in up to three currencies
 * in which two members describe the same money from two sides; read as a waterfall they
 * double-count (FR-014). They are rendered beside it, labelled as their own reading.
 */
import type {
  CandidateProjection,
  CostComponent,
  Money,
  NotStated,
  TupleOutcome,
} from "@/api/shapes";
import { quantity } from "@/design/format";

/** Where in the journey a bar sits. A closed vocabulary, rendered exhaustively. */
export type BarKind =
  | "outlay"
  | "way-in"
  | "arrived"
  | "purchase"
  | "accrued"
  | "remainder"
  | "released"
  | "tax"
  | "way-out"
  | "home";

export type Bar =
  | {
      readonly tag: "amount";
      readonly id: string;
      readonly kind: BarKind;
      readonly label: string;
      readonly amount: Money;
      /** The date the API dated this movement, where it dated one. */
      readonly on: string | null;
    }
  | {
      readonly tag: "refused";
      readonly id: string;
      readonly kind: BarKind;
      readonly label: string;
      readonly state: NotStated;
    }
  | {
      /**
       * The API said there was no such movement, which is a fact rather than an absence.
       *
       * `undeployed: null` is the answer saying the purchase deployed the whole of what
       * arrived. Rendering that as a refusal would read as *the engine could not say*, and
       * building a served `NotStated` for it here would be this client inventing a record the
       * API did not send.
       */
      readonly tag: "none";
      readonly id: string;
      readonly kind: BarKind;
      readonly label: string;
      readonly reason: string;
    }
  | {
      /** A tax bar: the charge, the base it was struck on, and the class that struck it. */
      readonly tag: "tax";
      readonly id: string;
      readonly kind: "tax";
      readonly label: string;
      readonly amount: Money;
      readonly base: Money;
      readonly taxClassId: string;
      readonly on: string | null;
    };

/**
 * Each term of a route's charge, in words and in the order the vocabulary declares them.
 *
 * A mapped type over the closed vocabulary rather than a lookup table: a fourth component the
 * API starts declaring leaves this literal one key short and the build red, instead of drawing
 * a bar with no label on it.
 */
const COMPONENTS: { readonly [Term in CostComponent]: string } = {
  conversion_spread: "the channel's spread",
  percentage_fee: "a percentage fee",
  fixed_fee: "a flat fee",
};

/**
 * Every bar of one candidate's waterfall, in money order.
 *
 * The outcome is read for the three figures the projection deliberately does not repeat — what
 * left the stream, what was left over, and what reached home — and for nothing else.
 */
export function barsOf(
  projection: CandidateProjection,
  outcome: TupleOutcome,
): readonly Bar[] {
  return [
    {
      tag: "amount",
      id: "outlay",
      kind: "outlay",
      label: "left the income stream",
      amount: outcome.outlay,
      on: outcome.span.start,
    },
    ...chargeBars("way-in", "the way in charged", projection.way_in.one_way.components, null),
    {
      tag: "amount",
      id: "arrived",
      kind: "arrived",
      label: "arrived at the venue",
      amount: projection.way_in.one_way.arrived,
      on: null,
    },
    ...purchaseBars(projection),
    premiumBar(projection),
    remainderBar(outcome),
    ...releasedBars(projection),
    ...taxBars(projection),
    ...exitBars(projection),
    {
      tag: "amount",
      id: "home",
      kind: "home",
      label: "reached a spendable endpoint",
      amount: outcome.reaches,
      on: outcome.span.end,
    },
  ];
}

/**
 * One bar per component of a route's charge, never one bar for their total.
 *
 * The costing splits the charge into the three terms that can charge anything and computes the
 * sum only to divide by it, so a total drawn here would be an addition with no owning call. A
 * component that is zero is drawn as a zero: the record states every member, and a reader who
 * saw two bars would not know whether the third was zero or absent.
 */
function chargeBars(
  kind: BarKind,
  label: string,
  components: CandidateProjection["way_in"]["one_way"]["components"],
  on: string | null,
): readonly Bar[] {
  return entriesOf(components).map(([term, amount]) => ({
    tag: "amount" as const,
    id: [kind, term, on ?? "once"].join(":"),
    kind,
    label: `${label} — ${termLabel(term)}`,
    amount,
    on,
  }));
}

/** The term's words, or the term itself where this client has no label for it (FR-021). */
function termLabel(term: string): string {
  const labels: Readonly<Record<string, string>> = COMPONENTS;
  return labels[term] ?? term;
}

function entriesOf(
  components: CandidateProjection["way_in"]["one_way"]["components"],
): readonly (readonly [string, Money])[] {
  const known = Object.keys(COMPONENTS);
  const inOrder = known.flatMap((term) => {
    const amount = components[term];
    return amount === undefined ? [] : [[term, amount] as const];
  });
  // FR-021's rule for a flow kind, applied to a component: a term this client has no label for
  // is drawn raw at the end rather than dropped. The mapping is open on the wire even though
  // the vocabulary that fills it is closed.
  const rest = Object.entries(components)
    .filter(([term]) => !known.includes(term))
    .sort(([one], [other]) => one.localeCompare(other));
  return [...inOrder, ...rest];
}

/**
 * What the purchase paid, at what price, and the split of that **price**.
 *
 * `Carried.clean` and `Carried.accrued` are struck on the **quotation**, so they are per unit —
 * `accrual.carried_to` is handed one unit's quote and `_acquire` multiplies afterwards. Drawing
 * them as parts of the total would report an accrual of 15.86 on a purchase that paid about 793
 * of it, so the price per unit is drawn between them and the total, the labels say *per unit*,
 * and the quantity is on the purchase bar. Scaling them here is not available: the total accrual
 * is a figure the engine never computed, and this client computes none.
 */
function purchaseBars(projection: CandidateProjection): readonly Bar[] {
  const purchase = projection.purchase;
  const bought: Bar = {
    tag: "amount",
    id: "purchase",
    kind: "purchase",
    label: `bought ${quantity(purchase.quantity)} unit(s)`,
    amount: purchase.paid,
    on: purchase.purchased_on,
  };
  const priced: Bar = {
    tag: "amount",
    id: "price",
    kind: "purchase",
    label: "at a price per unit of",
    amount: purchase.price_per_unit,
    on: purchase.purchased_on,
  };
  if (purchase.carried.tag === "card.NotStated") {
    return [
      bought,
      priced,
      {
        tag: "refused",
        id: "accrued",
        kind: "accrued",
        label: "accrued interest inside the price per unit",
        state: purchase.carried,
      },
    ];
  }
  return [
    bought,
    priced,
    {
      tag: "amount",
      id: "accrued:clean",
      kind: "accrued",
      label: "of which, per unit, the clean price",
      amount: purchase.carried.clean,
      on: purchase.purchased_on,
    },
    {
      tag: "amount",
      id: "accrued:accrued",
      kind: "accrued",
      label: "of which, per unit, accrued interest paid to the seller",
      amount: purchase.carried.accrued,
      on: purchase.purchased_on,
    },
  ];
}

/** What the purchase could not deploy, from the outcome's own record. */
function remainderBar(outcome: TupleOutcome): Bar {
  const remainder = outcome.undeployed;
  if (remainder === null) {
    return {
      tag: "none",
      id: "remainder",
      kind: "remainder",
      label: "left over by the purchase",
      reason:
        "the arriving amount bought whole units with nothing left over, so no remainder made " +
        "the trip and none had to come home",
    };
  }
  return {
    tag: "amount",
    id: "remainder",
    kind: "remainder",
    label: "left over by the purchase",
    amount: remainder.amount,
    on: null,
  };
}

/**
 * What was paid over or under the principal the paper repays — or the arm saying it states none.
 *
 * A real term that reached no reader before this feature, and the clearest case of FR-016: a bar
 * a bond has and a fund does not is a **refusal** carrying the arm's own reason, never a zero and
 * never an absent row.
 */
function premiumBar(projection: CandidateProjection): Bar {
  const arm = projection.arm;
  if (arm.tag !== "card.BondArm") {
    return {
      tag: "refused",
      id: "premium",
      kind: "purchase",
      label: "paid over or under the principal repaid",
      state: arm.at_purchase,
    };
  }
  return {
    tag: "amount",
    id: "premium",
    kind: "purchase",
    label: "paid over or under the principal repaid",
    amount: arm.at_purchase.difference,
    on: projection.purchase.purchased_on,
  };
}

/** One bar per dated flow the holding released, gross. The purchase is not one of them. */
function releasedBars(projection: CandidateProjection): readonly Bar[] {
  return projection.flows
    .filter((flow) => flow.kind !== "purchase")
    .map((flow) => ({
      tag: "amount" as const,
      id: `released:${String(flow.sequence)}`,
      kind: "released" as const,
      label: `the holding released — ${flow.kind.replace(/_/g, " ")}`,
      amount: flow.gross,
      on: flow.occurred_on,
    }));
}

/** One bar per charge: its own total, with the base it was struck on beside it (FR-004). */
function taxBars(projection: CandidateProjection): readonly Bar[] {
  return projection.charges.map((charge) => ({
    tag: "tax" as const,
    id: `tax:${String(charge.event_sequence)}`,
    kind: "tax" as const,
    label: "tax struck on it",
    amount: charge.total,
    base: charge.taxable_base,
    taxClassId: charge.tax_class_id,
    on: dateOfEvent(projection, charge.event_sequence),
  }));
}

function dateOfEvent(projection: CandidateProjection, sequence: number): string | null {
  return projection.flows.find((flow) => flow.sequence === sequence)?.occurred_on ?? null;
}

/**
 * The way out's charge, **per dated release rather than per flow** (FR-013's last clause).
 *
 * A flat fee is charged per movement, so two lifecycle flows on one date travel home once and
 * share one charge. Splitting it between them would be a figure with no owning call; drawing one
 * bar per flow would report the fee twice.
 */
function exitBars(projection: CandidateProjection): readonly Bar[] {
  return projection.releases.flatMap((release) =>
    chargeBars(
      "way-out",
      "the way out charged",
      release.way_out.components,
      release.released_on,
    ),
  );
}
