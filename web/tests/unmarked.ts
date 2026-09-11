/**
 * Figure slots rendered as a bare value outside the one place a card may render one.
 *
 * A rendered figure is `marked` or it is `refused` — except a tax of `0.00` that **no rule ran
 * on**, which cites nothing and therefore has no mark to wear. Inventing one for it is the
 * fabrication that says *unverified* about a source nobody looked at; the `no-rule-ran` badge
 * beside it is the stronger statement, and this is what keeps the exception to that one case.
 */
export function unmarkedOutsideAnUncitedZero(container: HTMLElement): readonly string[] {
  return [...container.querySelectorAll("[data-figure='value']")]
    .filter((slot) => slot.closest("[data-tax-zero='no-rule-ran']") === null)
    .map((slot) => slot.textContent ?? "");
}
