/**
 * The drawn vocabulary: one hue, one icon and one word per kind (FR-001, FR-002, FR-004).
 *
 * The token names are written out rather than composed from the key. A name built as
 * `--kind-${kind}-ink` would name a token nobody declared the moment a key is renamed, and the
 * tile would render with no colour and no error; written out, the CSS is checkable against this
 * map (`tests/unit/kinds.test.ts`).
 */
import type { InstrumentDeclared } from "@/api/shapes";
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
};

const CLASS_WORDS: Readonly<Record<string, string>> = {
  enumerated_schedule: "payments enumerated",
  fixed_income: "terms declared",
  collective_investment_fund: "collective investment fund",
};

/** The declared class in words where this client has one for it, and the raw class where not. */
export function classWord(instrumentClass: string): string {
  return CLASS_WORDS[instrumentClass] ?? instrumentClass;
}

/** The class an instrument read declares, for the two reads that differ on carrying one. */
export function declaredClass(read: InstrumentDeclared): string | null {
  return read.tag === "interface.InstrumentDeclaration" ? read.instrument_class : null;
}
