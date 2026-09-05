/**
 * The two search parameters, validated per route.
 *
 * FR-020 and FR-027: an invalid value is a visible error naming the parameter, and no default is
 * ever silently substituted -- the same prohibition Principle IV puts on a malformed data field
 * one layer down. `as_of` is the only global one; the window belongs to the two series routes,
 * and there is no `display`: the switch is deferred by owner decision 2026-09-03.
 */
export type Parsed<Value> =
  | { readonly tag: "given"; readonly value: Value }
  | { readonly tag: "missing"; readonly parameter: string }
  | {
      readonly tag: "invalid";
      readonly parameter: string;
      readonly given: string;
      readonly reason: string;
    };

const DATE = /^\d{4}-\d{2}-\d{2}$/;
const PERIOD = /^\d{4}-\d{2}$/;

export function parseAsOf(raw: string | undefined): Parsed<string> {
  if (raw === undefined) return { tag: "missing", parameter: "as_of" };
  if (!DATE.test(raw) || Number.isNaN(Date.parse(raw))) {
    return {
      tag: "invalid",
      parameter: "as_of",
      given: raw,
      reason: "as_of is a calendar date as YYYY-MM-DD. No default is substituted for one that is not.",
    };
  }
  return { tag: "given", value: raw };
}

export type Window = { readonly from: string; readonly to: string };

/**
 * A window is two-ended, as the API's own refusal says: one end alone would leave the other to
 * be inferred, and the inference is what a coverage refusal exists to prevent.
 */
export function parseWindow(from: string | undefined, to: string | undefined): Parsed<Window> {
  if (from === undefined && to === undefined) return { tag: "missing", parameter: "from,to" };
  if (from === undefined || to === undefined) {
    return {
      tag: "invalid",
      parameter: "from,to",
      given: `${from ?? ""}..${to ?? ""}`,
      reason: "a window is two-ended: give both from and to, or neither.",
    };
  }
  const shaped = [from, to].filter((end) => !DATE.test(end) && !PERIOD.test(end));
  if (shaped.length > 0) {
    return {
      tag: "invalid",
      parameter: "from,to",
      given: `${from}..${to}`,
      reason: `${shaped.join(", ")} is neither a calendar date as YYYY-MM-DD nor a month as YYYY-MM.`,
    };
  }
  if (from > to) {
    return {
      tag: "invalid",
      parameter: "from,to",
      given: `${from}..${to}`,
      reason: "the window ends before it begins.",
    };
  }
  return { tag: "given", value: { from, to } };
}

/**
 * What a route reads out of the URL, as the text the reader typed.
 *
 * The router's search parser coerces a numeric- or boolean-looking value before `validateSearch`
 * sees it, so `?as_of=20260905` arrives as a number. Mapping that to `undefined` would make it
 * indistinguishable from an absent parameter, and the route would then redirect with today's
 * date -- the silent default substitution FR-020 forbids, arriving one layer up. Everything that
 * is present is therefore returned as text and refused by the validator instead.
 */
export function stringOrUndefined(value: unknown): string | undefined {
  if (value === undefined) return undefined;
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}
