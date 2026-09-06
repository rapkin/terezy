/**
 * Answer fixtures, typed from the generated document (021 FR-044).
 *
 * The shapes and the figures are the ones the shipped registry produces, read off
 * `GET /api/questions/fifty-thousand-hryvnia/answer?as_of=2026-09-05` on 2026-09-06 — a fixture
 * that has drifted from the contract fails to **compile** rather than passing.
 */
import type {
  Comparison,
  DateRange,
  DominanceResult,
  HorizonSection,
  Money,
  PairYieldedNoCandidate,
  Question,
  RefusedTuple,
  Tuple,
  TupleOutcome,
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
}): TupleOutcome {
  return {
    tag: "tuple.TupleOutcome",
    key: tuple(over.instrumentId),
    outlay: money(50000, []),
    parts: [],
    arrivals: [],
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
}): Comparison {
  return {
    tag: "tuple.Comparison",
    ranked: [...over.ranked],
    benchmark: over.benchmark ?? 0,
    beats_benchmark: [...(over.beats ?? [])],
    ties: (over.ties ?? []).map((held) => [...held]),
    refused: [...(over.refused ?? [])],
    not_comparable: [],
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
  readonly separating?: DominanceResult["separating"];
  readonly indistinguishable?: DominanceResult["indistinguishable"];
  readonly standing?: DominanceResult["benchmark_standing"];
}): DominanceResult {
  return {
    tag: "dominance.DominanceResult",
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
