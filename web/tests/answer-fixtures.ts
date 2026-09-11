/**
 * Answer fixtures, typed from the generated document (021 FR-044).
 *
 * The shapes and the figures are the ones the shipped registry produces, read off
 * `GET /api/questions/fifty-thousand-hryvnia/answer?as_of=2026-09-05` on 2026-09-06 — a fixture
 * that has drifted from the contract fails to **compile** rather than passing.
 */
import type {
  Answer,
  Comparison,
  HeldPosition,
  DateRange,
  DominanceResult,
  HorizonSection,
  Money,
  PairYieldedNoCandidate,
  Question,
  RefusedTuple,
  Tuple,
  TupleOutcome,
  UndeployedCash,
} from "@/api/shapes";
import { tagOf } from "@/lib/narrow";
import { money, provenance, source, verdict } from "./fixtures";

export const HORIZON: DateRange = {
  tag: "interface.DateRange",
  start: "2026-09-01",
  end: "2026-10-01",
};

export function range(start: string, end: string): DateRange {
  return { tag: "interface.DateRange", start, end };
}

export function tuple(instrumentId: string, streamId = "salary_uah"): Tuple {
  return {
    tag: "tuple.Tuple",
    instrument_id: instrumentId,
    stream_id: streamId,
    route_in: {
      tag: "path.FundingPath",
      destination_id: "inzhur",
      stream_id: streamId,
      route_id: "inzhur_direct",
    },
    exit_terms: {
      tag: "interface.Assumptions",
      consumption_method: "fifo",
      coupon_policy: "hold_cash",
    },
    route_out: { tag: "path.DeclaredExit", route_id: "inzhur_to_monobank" },
  };
}

export function outcome(over: {
  readonly instrumentId: string;
  readonly reaches?: Money;
  readonly rate?: TupleOutcome["implied_rate"];
  readonly soldEarly?: TupleOutcome["sold_early"];
  readonly span?: DateRange;
  readonly restsOn?: readonly string[];
  readonly undeployed?: TupleOutcome["undeployed"];
  readonly quotation?: TupleOutcome["carried_quotation"];
  readonly arrivals?: TupleOutcome["arrivals"];
}): TupleOutcome {
  return {
    tag: "tuple.TupleOutcome",
    key: tuple(over.instrumentId),
    outlay: money(50000, []),
    parts: [],
    arrivals: [...(over.arrivals ?? [arrival("2026-10-04")])],
    reaches: over.reaches ?? money(50529.090769230774, [source()]),
    implied_rate: over.rate ?? { tag: "rates.NominalRate", value: 0.18112850290026622 },
    real: {
      tag: "hurdle.RealTerms",
      assumed: { tag: "rates.RealTermsUnavailable", reason: "no CPI forecast is declared" },
      realized: { tag: "rates.RealTermsUnavailable", reason: "no CPI observation covers it" },
    },
    span: over.span ?? range("2026-09-01", "2026-10-04"),
    horizon: HORIZON,
    routes: {
      tag: "tuple.RouteStanding",
      status: "open",
      constrained: [],
      disruption_probability: 0,
    },
    risk_class: "sovereign_local",
    accounts_for: ["tax on every taxable event over the holding's life"],
    rests_on: [...(over.restsOn ?? ["the plan's own choices"])],
    excludes: [],
    sold_early: over.soldEarly ?? null,
    carried_quotation: over.quotation ?? null,
    undeployed: over.undeployed ?? null,
    provenance: provenance([source()]),
    staleness: verdict([]),
  };
}

/** One arrival: money released at the far end and landing at a spendable endpoint. */
export function arrival(on: string): TupleOutcome["arrivals"][number] {
  return {
    tag: "tuple.Arrival",
    released_on: on,
    released: money(50000, [source()]),
    arrived_on: on,
    amount: money(50000, [source()]),
  };
}

/** The remainder rode the declared way out and arrived inside `reaches` (026 FR-016). */
export function cameHome(on = "2026-10-04"): UndeployedCash["journey"] {
  return {
    tag: "tuple.RemainderCameHome",
    left_on: "2026-09-01",
    arrived_on: on,
    reached: money(494.68, [source()]),
  };
}

/** The remainder the way out would not carry (026 FR-017). */
export function stayed(reason: string): UndeployedCash["journey"] {
  return { tag: "tuple.RemainderStayed", reason };
}

export const SOLD_EARLY: NonNullable<TupleOutcome["sold_early"]> = {
  tag: "early_exit.SoldEarly",
  on: "2026-10-01",
  quoted_on: "2026-08-24",
  units: 49,
  price_per_unit: money(1030.4, [source()]),
  clean_per_unit: money(1010.2, [source()]),
  accrued_per_unit: money(20.2, [source()]),
  proceeds: money(50489.6, [source()]),
  assumption: {
    tag: "quotation.QuotationHolds",
    id: "the_clean_price_holds",
    is_assumption: true,
    rationale: "OWNER'S BELIEF, not an observation.",
  },
};

export function comparison(over: {
  readonly ranked: readonly TupleOutcome[];
  readonly benchmark?: number;
  readonly beats?: readonly number[];
  readonly ties?: readonly (readonly number[])[];
  readonly refused?: readonly RefusedTuple[];
  readonly notComparable?: readonly TupleOutcome[];
}): Comparison {
  return {
    tag: "tuple.Comparison",
    ranked: [...over.ranked],
    benchmark: over.benchmark ?? 0,
    beats_benchmark: [...(over.beats ?? [])],
    ties: (over.ties ?? []).map((held) => [...held]),
    refused: [...(over.refused ?? [])],
    not_comparable: [...(over.notComparable ?? [])],
    continuation: "hold_as_cash",
    horizon: HORIZON,
  };
}

export function refusedTuple(instrumentId: string, reason: string): RefusedTuple {
  return {
    tag: "tuple.RefusedTuple",
    key: tuple(instrumentId),
    refusal: { tag: "tuple.InstrumentRefused", instrument_id: instrumentId, reason },
  };
}

export function noCandidate(
  instrumentId: string,
  over: { readonly streamId?: string; readonly side?: "route_in" | "route_out" } = {},
): PairYieldedNoCandidate {
  return {
    tag: "candidates.PairYieldedNoCandidate",
    instrument_id: instrumentId,
    stream_id: over.streamId ?? "contract_usd",
    why: {
      tag: "candidates.NothingConnects",
      side: over.side ?? "route_in",
      reason: `no declared inbound route carries money to '${instrumentId}'.`,
    },
  };
}

export function dominance(over: {
  readonly nonDominated: readonly Tuple[];
  readonly evaluated?: number;
  readonly separating?: DominanceResult["separating"];
  readonly indistinguishable?: DominanceResult["indistinguishable"];
  readonly standing?: DominanceResult["benchmark_standing"];
}): DominanceResult {
  return {
    tag: "dominance.DominanceResult",
    evaluated_count: over.evaluated ?? over.nonDominated.length,
    non_dominated: [...over.nonDominated],
    dominated: [],
    not_placed: [],
    incomparable: [],
    indistinguishable: [...(over.indistinguishable ?? [])],
    benchmark_standing: over.standing ?? {
      tag: "dominance.NothingDominatesTheHurdle",
      key: tuple("UA4000231195"),
    },
    separating: over.separating ?? { tag: "dominance.NoStatedAssumptionSeparatesThem" },
    objectives: {
      tag: "objectives.ObjectiveSet",
      id: "money-and-when",
      owner_id: "owner-001",
      objectives: [],
    },
    resolved_bands: [],
  };
}

export function section(over: {
  readonly horizon?: DateRange;
  readonly outcome: HorizonSection["outcome"];
  readonly dominance: HorizonSection["dominance"];
  readonly standings?: HorizonSection["standings"];
  readonly reserves?: HorizonSection["reserves"];
}): HorizonSection {
  return {
    tag: "answer.HorizonSection",
    horizon: over.horizon ?? HORIZON,
    outcome: over.outcome,
    dominance: over.dominance,
    standings: [...(over.standings ?? [])],
    reserves: [...(over.reserves ?? [])],
    excludes: [],
    arrives_after_horizon: [],
  };
}

export function survey(over: {
  readonly comparison: Comparison;
  readonly noCandidates?: readonly PairYieldedNoCandidate[];
}): HorizonSection["outcome"] {
  return {
    tag: "candidates.CandidateSurvey",
    comparison: over.comparison,
    enumerated: {
      tag: "candidates.CandidateSet",
      candidates: [],
      no_candidate: [...(over.noCandidates ?? [])],
      pairs_considered: 26,
      question: {
        tag: "candidates.Question",
        amounts: { salary_uah: money(50000, []) },
        as_of: "2026-09-05",
        bound: { tag: "composed.SegmentBound", max_segments: 2 },
        horizon: HORIZON,
        subjects: ["ovdp"],
        continuation: "hold_as_cash",
        plans: {},
        regime_id: "(no regime declared)",
      },
      provenance: provenance([source()]),
      staleness: verdict([]),
    },
  };
}

/** One held position, valued, with the marks its parents carry. */
export const HELD: HeldPosition = {
  tag: "held.HeldPosition",
  instrument_id: "btc",
  name: "Bitcoin",
  venue_id: "binance",
  quantity: 0.04,
  quantity_unit: "BTC",
  basis: money(96000, [source()]),
  lots: [
    {
      tag: "held.HeldLot",
      lot_id: "btc-1",
      quantity: 0.04,
      acquired_on: "2025-03-11",
      declared_at: "2026-09-02",
      basis: money(96000, [source()]),
      struck_from: null,
    },
  ],
  // As the API produces one: the value struck in the **price** currency, the base-currency
  // restatement beside it, and the peg the dollar figure rests on. A fixture in one currency
  // throughout is a shape no declared held asset has, and a test over it compares nothing.
  valuation: {
    tag: "held.Valued",
    value: { ...money(3120, [source()]), currency: "USD" },
    quotation: {
      tag: "quotations.Quotation",
      on_date: "2026-09-05",
      close: 78000,
      provenance: provenance([source()]),
    },
    in_base: {
      tag: "held.InBaseCurrency",
      value: money(128000, [source()]),
      nominal_change: money(32000, [source()]),
      struck: null,
    },
    assumption: {
      tag: "quote_asset.QuoteAssetIsWorth",
      id: "usdt_is_a_dollar",
      quote_asset: "USDT",
      currency: "USD",
      is_assumption: true,
      rationale: "OWNER'S BELIEF: one USDT is taken as one dollar, and no peg break is modelled.",
    },
  },
  rank: {
    tag: "held.NotRankedAgainstTheBenchmark",
    instrument_id: "btc",
    reason: "the question is what to do with money not yet spent.",
  },
  tax: {
    tag: "held.NoTaxUntilADisposal",
    instrument_id: "btc",
    tax_class_id: "ua_investment_income",
    reason: "nothing is owed until a disposal.",
  },
  yields: {
    tag: "held.NoYieldIsDeclared",
    instrument_id: "btc",
    reason: "no yield is declared for a held asset.",
  },
  provenance: provenance([source()]),
};

/** A whole answer, for the components that take one. */
export function answer(over: {
  readonly subjects?: Answer["subjects"];
  readonly sections?: readonly HorizonSection[];
  readonly held?: Answer["held"];
  readonly question?: Question;
} = {}): Answer {
  return {
    tag: "answer.Answer",
    as_of: "2026-09-05",
    question: over.question ?? question(),
    subjects: [...(over.subjects ?? [])],
    sections: [...(over.sections ?? [])],
    held: [...(over.held ?? [])],
    excludes: [],
    provenance: provenance([source()]),
    staleness: verdict([]),
  };
}

export function question(over: Partial<Question> = {}): Question {
  return {
    tag: "question.Question",
    id: "fifty-thousand-hryvnia",
    owner_id: "owner-001",
    asked_on: "2026-08-30",
    regime_id: "(no regime declared)",
    continuation: "hold_as_cash",
    amounts: { salary_uah: money(50000, []), contract_usd: { ...money(1, []), currency: "USD" } },
    subjects: ["cash", "ovdp", "inzhur", "btc"],
    every_declared_instrument: false,
    horizons: [HORIZON],
    objective_set_id: "money-and-when",
    benchmark_instrument_id: "UA4000231195",
    plans: {},
    reserves: [],
    ...over,
  };
}

/**
 * An outcome as it arrives off the wire, for the member the generated types do not know about.
 *
 * The client decodes `unknown` and narrows, so a tag added to `sold_early` upstream is a shape
 * it can meet before its own types have caught up — and FR-019's raw-tag arm is only reachable
 * from here. Narrowed by a predicate and never cast: a cast would assert the very thing the
 * test is about.
 */
export function servedOutcome(body: object): TupleOutcome {
  const parsed: unknown = JSON.parse(JSON.stringify(body));
  if (!isOutcomeShaped(parsed)) throw new Error("the fixture is not an outcome");
  return parsed;
}

function isOutcomeShaped(value: unknown): value is TupleOutcome {
  return tagOf(value) === "tuple.TupleOutcome";
}
