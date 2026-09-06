/**
 * FR-026: money, rates and dates are rendered here and nowhere else.
 *
 * The precision is a **rendering** precision and never a comparison tolerance: nothing in this
 * client compares two figures for closeness — `ties` and `beats_benchmark` are struck in the
 * engine, at the project tolerance. This module closes the web half of `cli-renders-raw-floats`,
 * where an amount reached a reader as `49834.350000000006` and a rate as `3.7e-16`.
 */
import type { Currency, Money, NominalRate } from "@/api/shapes";
import { assertNever } from "@/lib/exhaustive";

/** Money is stated to the kopeck: the smallest unit either declared currency has. */
const MONEY_DECIMALS = 2;

/** A rate is stated to two decimals of a percent. */
const RATE_DECIMALS = 2;

/** U+2009. A grouping mark that is not a comma or a full stop, so neither can be read as one. */
export const GROUP = " ";

const MONTHS = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
];

/**
 * The symbol for each declared currency.
 *
 * A `switch` over the closed `Currency` union rather than a lookup: a third currency the API
 * starts sending turns this red instead of rendering an amount with no unit on it.
 */
export function currencySymbol(currency: Currency): string {
  switch (currency) {
    case "UAH":
      return "₴";
    case "USD":
      return "$";
  }
  assertNever(currency);
}

function grouped(digits: string): string {
  let out = "";
  for (let at = digits.length; at > 0; at -= 3) {
    const from = Math.max(0, at - 3);
    out = digits.slice(from, at) + (out === "" ? "" : GROUP + out);
  }
  return out;
}

function fixed(value: number, decimals: number): string {
  const sign = value < 0 || Object.is(value, -0) ? "-" : "";
  const [whole = "0", fraction = ""] = Math.abs(value).toFixed(decimals).split(".");
  return `${sign}${grouped(whole)}${fraction === "" ? "" : `.${fraction}`}`;
}

/** An amount, in the currency the API returned it in. Nothing here converts one to another. */
export function money(value: Money): string {
  return `${fixed(value.amount, MONEY_DECIMALS)}${GROUP}${currencySymbol(value.currency)}`;
}

/** A nominal rate as a percent. */
export function rate(value: NominalRate): string {
  return `${fixed(value.value * 100, RATE_DECIMALS)}${GROUP}%`;
}

/** A count of members the API sent. Whole by construction; grouped so a large one is readable. */
export function count(value: number): string {
  return grouped(Math.trunc(value).toString());
}

/**
 * An ISO date as `4 Oct 2026`.
 *
 * Parsed by splitting rather than by `Date`, which is FR-021a's rule and also the correct one
 * here: `new Date("2026-10-04")` is UTC midnight and renders as the day before in any negative
 * offset. A string that is not an ISO date is returned unchanged rather than rendered as a
 * plausible wrong day.
 */
export function day(iso: string): string {
  const parts = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso);
  if (parts === null) return iso;
  const [, year = "", month = "", date = ""] = parts;
  const name = MONTHS[Number(month) - 1];
  if (name === undefined) return iso;
  return `${String(Number(date))} ${name} ${year}`;
}
