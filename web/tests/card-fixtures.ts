/**
 * Projection fixtures, typed from the generated document (021 FR-044).
 *
 * The shapes and the figures are the ones the shipped registry produces, read off
 * `GET /api/questions/fifty-thousand-hryvnia/candidates/{key}?as_of=2026-09-06` on 2026-09-11 —
 * a fixture that has drifted from the contract fails to **compile** rather than passing.
 */
import type {
  BondArm,
  CandidateProjection,
  CashArm,
  CostComponents,
  FlowLine,
  FundArm,
  Money,
  NotStated,
  Release,
  TaxCharge,
  WayIn,
} from "@/api/shapes";
import { money, provenance, source } from "./fixtures";

export const KEY = "2026-09-01..2026-10-01|UA4000231195|salary_uah|inzhur_direct|out|Assumptions";

export function notStated(what: string, arm = "bond"): NotStated {
  return {
    tag: "card.NotStated",
    what,
    arm,
    reason: `the ${arm} arm states no ${what}, so there is no flow to draw one from.`,
  };
}

export function usd(amount: number): Money {
  return { ...money(amount, [source()]), currency: "USD" };
}

export function components(over: Partial<Record<string, Money>> = {}): CostComponents {
  return {
    conversion_spread: money(0, [source()]),
    percentage_fee: money(12.5, [source()]),
    fixed_fee: money(5, [source()]),
    ...over,
  };
}

export function flow(over: Partial<FlowLine> & { readonly sequence: number }): FlowLine {
  return {
    tag: "card.FlowLine",
    occurred_on: "2026-10-01",
    kind: "coupon",
    quantity: null,
    gross: money(500, [source()]),
    tax: money(0, [source()]),
    net: money(500, [source()]),
    conventions: {
      tag: "conventions.ConventionsApplied",
      periodicity: "semiannual",
      day_count: "act/365",
      business_day_rule: "following",
    },
    caused_by: {
      tag: "events.CausationRef",
      kind: "instrument_term",
      id: "UA4000231195",
      detail: "a declared coupon",
    },
    ...over,
  };
}

/** A tax line no rule ran on: a zero resting on no source at all (E11's second case). */
export function uncitedZero(): Money {
  return { ...money(0, []), provenance: provenance([]) };
}

/** A zero **charge** citing the exemption that struck it (E11's first case). */
export function citedZero(): Money {
  return money(0, [source({ id: "tax/ua.toml#ua_government_bond", kind: "tax_rate" })]);
}

export function charge(over: Partial<TaxCharge> = {}): TaxCharge {
  return {
    tag: "interface.TaxCharge",
    event_sequence: 2,
    pit: citedZero(),
    levy: citedZero(),
    total: citedZero(),
    taxable_base: money(500, [source()]),
    tax_class_id: "ua_government_bond",
    charged_for_year: 2026,
    provenance: provenance([source({ id: "tax/ua.toml#ua_government_bond" })]),
    ...over,
  };
}

export function wayIn(over: Partial<WayIn> = {}): WayIn {
  return {
    tag: "card.WayIn",
    latency_days: 1,
    one_way: {
      tag: "ramp.OneWayCost",
      sent: money(50000, [source()]),
      arrived: money(49982.5, [source()]),
      components: components(),
      fraction: 0.00035,
      spreads_over_reference: [],
      channels_applied: [],
      provenance: provenance([source()]),
      staleness: { tag: "staleness.StalenessVerdict", assessed: [], stale: [] },
      by_segment: [],
    },
    ...over,
  };
}

export function release(over: Partial<Release> = {}): Release {
  return {
    tag: "card.Release",
    released_on: "2026-10-01",
    arrived_on: "2026-10-04",
    way_out: {
      tag: "ramp.WayOutCost",
      path: {
        tag: "path.FundingPath",
        destination_id: "monobank_uah",
        stream_id: "salary_uah",
        route_id: "inzhur_to_monobank",
      },
      sent: money(500, [source()]),
      arrived: money(494, [source()]),
      components: components(),
      fraction: 0.012,
      spreads_over_reference: [],
      channels_applied: [],
      provenance: provenance([source()]),
      staleness: { tag: "staleness.StalenessVerdict", assessed: [], stale: [] },
      by_segment: [],
      latency_days: 3,
      status: "open",
      disruption_probability: 0.01,
      ceiling: null,
    },
    ...over,
  };
}

export function bondArm(over: Partial<BondArm> = {}): BondArm {
  return {
    tag: "card.BondArm",
    at_purchase: {
      tag: "project.PurchasePremium",
      paid: money(49299.21, [source()]),
      principal_returned: money(49833.56, [source()]),
      difference: money(-534.35, [source()]),
      tax_class_id: "ua_government_bond",
      governed_by: {
        tag: "project.GovernedBy",
        category_id: "ua_government_bond",
        treatment: "exempt",
        reason: "the declared class exempts it",
      },
    },
    distributions: notStated("distributions"),
    exit_line: notStated("exit_line"),
    ...over,
  };
}

export function fundArm(over: Partial<FundArm> = {}): FundArm {
  return {
    tag: "card.FundArm",
    distributions: [],
    exit_line: notStated("exit_line", "fund"),
    entry_spread: money(0, [source()]),
    exit_spread: money(0, [source()]),
    at_purchase: notStated("at_purchase", "fund"),
    ...over,
  };
}

export function cashArm(over: Partial<CashArm> = {}): CashArm {
  return {
    tag: "card.CashArm",
    released: money(50000, [source()]),
    at_purchase: notStated("at_purchase", "cash"),
    distributions: notStated("distributions", "cash"),
    exit_line: notStated("exit_line", "cash"),
    ...over,
  };
}

export function projection(over: Partial<CandidateProjection> = {}): CandidateProjection {
  return {
    tag: "card.CandidateProjection",
    projection_key: KEY,
    instrument_id: "UA4000231195",
    arm: bondArm(),
    flows: [
      flow({
        sequence: 1,
        kind: "purchase",
        occurred_on: "2026-09-02",
        gross: money(-49299.21, [source()]),
        tax: uncitedZero(),
        net: money(-49299.21, [source()]),
        quantity: 50,
      }),
      flow({ sequence: 2, kind: "redemption", occurred_on: "2026-10-01" }),
    ],
    charges: [charge()],
    purchase: {
      tag: "card.Purchase",
      purchased_on: "2026-09-02",
      quantity: 50,
      price_per_unit: money(985.98, [source()]),
      paid: money(49299.21, [source()]),
      carried: {
        tag: "accrual.Carried",
        clean: money(970.12, [source()]),
        accrued: money(15.86, [source()]),
      },
    },
    way_in: wayIn(),
    releases: [release()],
    ...over,
  };
}
