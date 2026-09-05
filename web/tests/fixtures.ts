/**
 * Fixtures typed from the generated document.
 *
 * FR-044: a fixture that has drifted from the contract fails to **compile** rather than passing,
 * which is the whole reason none of these is a hand-written response shape.
 */
import type {
  CategorySummary,
  FieldDescription,
  Money,
  Observation,
  Provenance,
  RecordRead,
  RegistrySummary,
  SourceRef,
  StaleSource,
  StalenessVerdict,
} from "@/api/shapes";

export function source(over: Partial<SourceRef> = {}): SourceRef {
  return {
    tag: "provenance.SourceRef",
    id: "instruments/UA1.toml#terms",
    citation: "https://bank.gov.ua/depo_securities?json — retrieved 2026-08-31",
    retrieved_on: "2026-08-31",
    verified_on: null,
    kind: "bond_terms",
    ...over,
  };
}

export function provenance(sources: readonly SourceRef[]): Provenance {
  return {
    tag: "provenance.Provenance",
    sources: [...sources],
    is_unverified: sources.some((held) => held.verified_on === null),
  };
}

export function money(amount: number, sources: readonly SourceRef[]): Money {
  return {
    tag: "money.Money",
    amount,
    currency: "UAH",
    provenance: provenance(sources),
  };
}

export function staleSource(over: Partial<StaleSource> = {}): StaleSource {
  return {
    tag: "staleness.StaleSource",
    source_id: "instruments/UA1.toml#terms",
    kind_id: "bond_terms",
    retrieved_on: "2026-08-31",
    age_days: 100,
    threshold_days: 30,
    overdue_days: 70,
    ...over,
  };
}

export function verdict(stale: readonly StaleSource[]): StalenessVerdict {
  return {
    tag: "staleness.StalenessVerdict",
    assessed: stale.map((held) => held.source_id),
    stale: [...stale],
  };
}

export function field(over: Partial<FieldDescription> & { name: string }): FieldDescription {
  return { tag: "envelopes.FieldDescription", kind: "scalar", of: [], optional: false, ...over };
}

export function cpiObservation(period: string, value: number, verified = false): Observation {
  return {
    tag: "series.CpiObservation",
    period,
    value,
    kind: "cpi_index",
    provenance: provenance([source({ id: `cpi/ua.toml#${period}`, verified_on: verified ? "2026-01-01" : null })]),
  };
}

export function rateObservation(onDate: string, value: number): Observation {
  return {
    tag: "official_rate.OfficialRateObservation",
    on_date: onDate,
    value,
    provenance: provenance([source({ id: `official_rates/x.toml#${onDate}` })]),
  };
}

export type InstrumentRead = Extract<RecordRead, { tag: "envelopes.ReadOfInstruments" }>;

type InstrumentDeclaration = Extract<
  InstrumentRead["result"],
  { tag: "interface.InstrumentDeclaration" }
>;

export function declaration(faceValue = 1000): InstrumentDeclaration {
  return {
    tag: "interface.InstrumentDeclaration",
    id: "UA1",
    name: "a bond",
    instrument_class: "enumerated_schedule",
    currency: "UAH",
    is_synthetic: false,
    terms: {
      tag: "interface.EnumeratedTerms",
      face_value: money(faceValue, [source()]),
      covers_from: "2026-01-01",
      payments: [],
      day_count: "act/365",
      published_in_order: null,
      provenance: provenance([source()]),
    },
    constraints: {
      tag: "interface.InstrumentConstraints",
      min_ticket: money(1000, [source()]),
      min_unit: 1,
      provenance: provenance([source()]),
    },
    tax_classes: {},
    groups: [],
  };
}

export function instrumentRead(over: Partial<InstrumentRead> = {}): InstrumentRead {
  return {
    tag: "envelopes.ReadOfInstruments",
    category: "instruments",
    as_of: "2026-09-05",
    scenario_id: null,
    declared_in: "instruments/UA1.toml",
    fields: [
      field({ name: "id" }),
      field({ name: "name" }),
      field({ name: "is_synthetic" }),
      field({ name: "terms", kind: "union", of: ["interface.EnumeratedTerms"] }),
      field({ name: "constraints", kind: "record", of: ["interface.InstrumentConstraints"] }),
    ],
    result: declaration(),
    ...over,
  };
}

export function keyedSummary(over: Partial<Extract<CategorySummary, { tag: "summary.KeyedSummary" }>> = {}) {
  return {
    tag: "summary.KeyedSummary" as const,
    category: "instruments",
    directory: "instruments",
    citations: { tag: "citation_policy.CitationsRequired" as const, path: "instruments" },
    declared_ids: 26,
    files: [{ tag: "summary.FileRef" as const, file: "instruments/UA1.toml", version: "sha256:aa" }],
    provenance: provenance([source()]),
    unverified_sources: 1,
    ...over,
  };
}

export function singletonSummary(
  over: Partial<Extract<CategorySummary, { tag: "summary.SingletonSummary" }>> = {},
) {
  return {
    tag: "summary.SingletonSummary" as const,
    category: "seeds",
    directory: "seeds",
    citations: {
      tag: "citation_policy.CitationsExempt" as const,
      path: "seeds",
      reason: "this directory holds the owner's own statements",
    },
    resolved: true,
    files: [],
    provenance: provenance([]),
    unverified_sources: 0,
    ...over,
  };
}

export function registry(categories: readonly CategorySummary[]): RegistrySummary {
  return {
    tag: "summary.RegistrySummary",
    as_of: "2026-09-05",
    scenario_id: null,
    categories: [...categories],
  };
}
