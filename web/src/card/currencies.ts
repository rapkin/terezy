/**
 * FR-015: are all the bars in one currency?
 *
 * A **boolean** and a list of currency tags, and nothing else. Where the answer is no the card
 * groups per currency, states why, and consults no rate — the display switch is deferred and
 * every declared channel's reference rate is a synthetic fixture, so a joined baseline would be
 * a conversion at a number nobody declared.
 */
import type { Currency } from "@/api/shapes";
import type { Bar } from "./bars";

/** Every currency the bars are in, in the order they first appear. No amount is read. */
export function currenciesOf(bars: readonly Bar[]): readonly Currency[] {
  const seen: Currency[] = [];
  for (const bar of bars) {
    if (bar.tag === "refused" || bar.tag === "none") continue;
    if (!seen.includes(bar.amount.currency)) seen.push(bar.amount.currency);
  }
  return seen;
}

/** Whether one connected waterfall is drawable at all. */
export function sharesOneCurrency(bars: readonly Bar[]): boolean {
  return currenciesOf(bars).length <= 1;
}

/** The bars of one currency, for the grouped rendering. Still no amount read and no rate. */
export function inCurrency(bars: readonly Bar[], currency: Currency): readonly Bar[] {
  return bars.filter(
    (bar) => bar.tag === "refused" || bar.tag === "none" || bar.amount.currency === currency,
  );
}
