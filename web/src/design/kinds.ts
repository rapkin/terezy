/**
 * The drawn vocabulary: one hue, one icon and one word per kind (FR-001, FR-002, FR-004).
 *
 * The token names are written out rather than composed from the key. A name built as
 * `--kind-${kind}-ink` would name a token nobody declared the moment a key is renamed, and the
 * tile would render with no colour and no error; written out, the CSS is checkable against this
 * map (`tests/unit/kinds.test.ts`).
 */
import type { InstrumentDeclared, VenueKind } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";
import type { IconComponent } from "./icons/outline";
import {
  BankIcon,
  BondIcon,
  BrokerIcon,
  CashIcon,
  ExchangeIcon,
  FundIcon,
  HeldAssetIcon,
  IncomeStreamIcon,
  PayrollIcon,
  PlatformIcon,
  SpendableEndpointIcon,
} from "./icons/outline";

export type Kind =
  | "bond"
  | "fund"
  | "cash"
  | "held_asset"
  | "income_stream"
  | "spendable_endpoint"
  | "bank"
  | "exchange"
  | "broker"
  | "platform"
  | "payroll";

export type KindStyle = {
  /** FR-002: the kind carried in text, so hue is never the only thing saying what this is. */
  readonly word: string;
  readonly ink: string;
  readonly tint: string;
  readonly Icon: IconComponent;
};

export const KINDS: { readonly [K in Kind]: KindStyle } = {
  bond: { word: "bond", ink: "var(--kind-bond-ink)", tint: "var(--kind-bond-tint)", Icon: BondIcon },
  fund: { word: "fund", ink: "var(--kind-fund-ink)", tint: "var(--kind-fund-tint)", Icon: FundIcon },
  cash: { word: "cash", ink: "var(--kind-cash-ink)", tint: "var(--kind-cash-tint)", Icon: CashIcon },
  held_asset: {
    word: "held asset",
    ink: "var(--kind-held-asset-ink)",
    tint: "var(--kind-held-asset-tint)",
    Icon: HeldAssetIcon,
  },
  income_stream: {
    word: "income stream",
    ink: "var(--kind-income-stream-ink)",
    tint: "var(--kind-income-stream-tint)",
    Icon: IncomeStreamIcon,
  },
  spendable_endpoint: {
    word: "spendable endpoint",
    ink: "var(--kind-spendable-endpoint-ink)",
    tint: "var(--kind-spendable-endpoint-tint)",
    Icon: SpendableEndpointIcon,
  },
  bank: { word: "bank", ink: "var(--kind-bank-ink)", tint: "var(--kind-bank-tint)", Icon: BankIcon },
  exchange: {
    word: "exchange",
    ink: "var(--kind-exchange-ink)",
    tint: "var(--kind-exchange-tint)",
    Icon: ExchangeIcon,
  },
  broker: {
    word: "broker",
    ink: "var(--kind-broker-ink)",
    tint: "var(--kind-broker-tint)",
    Icon: BrokerIcon,
  },
  platform: {
    word: "platform",
    ink: "var(--kind-platform-ink)",
    tint: "var(--kind-platform-tint)",
    Icon: PlatformIcon,
  },
  payroll: {
    word: "payroll",
    ink: "var(--kind-payroll-ink)",
    tint: "var(--kind-payroll-tint)",
    Icon: PayrollIcon,
  },
};

/**
 * Every drawn kind as a value, so a test can render each one.
 *
 * Checked against `KINDS`' own keys rather than trusted: this list and the map are two places
 * one fact is written, and the assertion is what stops them parting.
 */
export const EVERY_KIND: readonly Kind[] = [
  "bond",
  "fund",
  "cash",
  "held_asset",
  "income_stream",
  "spendable_endpoint",
  "bank",
  "exchange",
  "broker",
  "platform",
  "payroll",
];

/**
 * FR-006: which kind an instrument is drawn as comes from the **tag** of its read.
 *
 * A mapped type over that tag union, so a third declaration kind leaves this object one key
 * short and the build red. `instrument_class` cannot carry the same guard — it is `string` on
 * the core record and `string` in the document — which is why it names a word below and never a
 * hue, and why an unnamed class renders raw rather than as nothing.
 */
export const INSTRUMENT_KIND: { readonly [Tag in InstrumentDeclared["tag"]]: Kind } = {
  "interface.InstrumentDeclaration": "bond",
  "fund.FundDeclaration": "fund",
  "cash.CashDeclaration": "cash",
};

/**
 * FR-007: a venue's kind is a declared field, and the five it can be are the drawn five.
 *
 * A mapped type over the vocabulary the document publishes, so the day a sixth is declared in
 * `core/` the build is red here rather than a venue being drawn with no hue. Nothing on the
 * answer screen draws a venue — this binds the language, which is what the graph feature will
 * read.
 */
export const VENUE_KIND: { readonly [K in VenueKind]: Kind } = {
  bank: "bank",
  exchange: "exchange",
  broker: "broker",
  platform: "platform",
  payroll: "payroll",
};

const CLASS_WORDS: Readonly<Record<string, string>> = {
  enumerated_schedule: "payments enumerated",
  fixed_income: "terms declared",
  cash_balance: "a balance, released at what it was opened with",
};

/** The declared class in words where this client has one for it, and the raw class where not. */
export function classWord(instrumentClass: string): string {
  return CLASS_WORDS[instrumentClass] ?? instrumentClass;
}

/**
 * The class an instrument read declares, where its read carries one.
 *
 * A switch and not a field test: a fund's declaration consumes the class at load and answers
 * without it, so which reads carry one is a fact about the document — and a fourth read arriving
 * should turn this red rather than silently answer `null`.
 */
export function declaredClass(read: InstrumentDeclared): string | null {
  switch (read.tag) {
    case "interface.InstrumentDeclaration":
      return read.instrument_class;
    case "cash.CashDeclaration":
      return read.instrument_class;
    case "fund.FundDeclaration":
      return null;
  }
  assertNever(read);
}
