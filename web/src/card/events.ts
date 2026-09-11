/**
 * FR-020 to FR-024: the timeline, from served dates and served latencies.
 *
 * Three rules shape it. Events come from the **schedule**, not from the released series — a date
 * whose payment its own tax consumed exactly is absent from the second and present in the first,
 * and that is the coupon a reader most needs to see. An event outside the window is drawn
 * outside it and marked, never dropped and never clamped. A latency segment's length is the
 * **declared** days the API sent, never the gap between two dates: they are the same number
 * until the day a declaration changes and one of them is still right.
 *
 * The only arithmetic here is `positionOf`, which places a date on an axis. A position is a
 * layout decision and not a figure: it is never rendered as a number, and nothing downstream
 * reads it as one.
 */
import type { CandidateProjection, NotStated, TupleOutcome } from "@/api/shapes";
import { isAbsence } from "./refusals";

export type EventKind =
  | "money-leaves"
  | "purchase"
  | "flow"
  | "arrival"
  | "remainder-arrival"
  | "window-start"
  | "window-end";

export type TimelineEvent = {
  readonly id: string;
  readonly on: string;
  readonly kind: EventKind;
  /** The engine's own word for a flow, raw where the client has no label for it (FR-021). */
  readonly detail: string;
  readonly outside: boolean;
};

export type LatencySegment = {
  readonly id: string;
  readonly from: string;
  readonly to: string;
  /** The **declared** days, as the API sent them. */
  readonly days: number;
  readonly label: string;
};

export type RemainderMark =
  | { readonly tag: "came-home"; readonly on: string }
  | { readonly tag: "stayed"; readonly reason: string }
  | { readonly tag: "none" };

export type Timeline = {
  readonly window: { readonly start: string; readonly end: string };
  readonly events: readonly TimelineEvent[];
  readonly segments: readonly LatencySegment[];
  readonly remainder: RemainderMark;
};

const FLOW_LABELS: Readonly<Record<string, string>> = {
  purchase: "purchase",
  coupon: "coupon",
  distribution: "distribution",
  principal_repayment: "principal repaid",
  redemption: "redeemed",
};

export function timelineOf(
  projection: CandidateProjection,
  outcome: TupleOutcome,
): Timeline {
  const window = { start: outcome.horizon.start, end: outcome.horizon.end };
  const outside = (on: string) => on < window.start || on > window.end;
  const events: TimelineEvent[] = [
    {
      id: "window-start",
      on: window.start,
      kind: "window-start",
      detail: "the horizon opens",
      outside: false,
    },
    {
      id: "money-leaves",
      on: outcome.span.start,
      kind: "money-leaves",
      detail: "the money leaves the income stream",
      outside: outside(outcome.span.start),
    },
    {
      id: "purchase",
      on: projection.purchase.purchased_on,
      kind: "purchase",
      detail: "the purchase settles",
      outside: outside(projection.purchase.purchased_on),
    },
    ...projection.flows
      .filter((flow) => flow.kind !== "purchase")
      .map((flow) => ({
        id: `flow:${String(flow.sequence)}`,
        on: flow.occurred_on,
        kind: "flow" as const,
        detail: FLOW_LABELS[flow.kind] ?? flow.kind,
        outside: outside(flow.occurred_on),
      })),
    ...armEvents(projection, outside),
    ...projection.releases.map((release) => ({
      id: `arrival:${release.released_on}`,
      on: release.arrived_on,
      kind: "arrival" as const,
      detail: "reaches a spendable endpoint",
      outside: outside(release.arrived_on),
    })),
    ...remainderEvent(outcome, outside),
    {
      id: "window-end",
      on: window.end,
      kind: "window-end",
      detail: "the horizon closes",
      outside: false,
    },
  ];
  return {
    window,
    events: [...events].sort(byDate),
    segments: segmentsOf(projection, outcome),
    remainder: remainderOf(outcome),
  };
}

/**
 * The dates an arm states that its ledger does not carry.
 *
 * A fund's distribution declares a **record** date beside its pay date, and its exit line an
 * **execution** date beside its settlement; neither is a ledger event, and both are the dates a
 * reader checking *when* would ask about first. An arm that states none says so through the
 * absences beside the timeline rather than by drawing nothing.
 */
function armEvents(
  projection: CandidateProjection,
  outside: (on: string) => boolean,
): readonly TimelineEvent[] {
  const arm = projection.arm;
  if (arm.tag !== "card.FundArm") return [];
  const distributions = arm.distributions.map((line) => ({
    id: `record-date:${line.record_on}`,
    on: line.record_on,
    kind: "flow" as const,
    detail: "the distribution's record date",
    outside: outside(line.record_on),
  }));
  const exit = arm.exit_line;
  if (exit.tag === "card.NotStated") return distributions;
  return [
    ...distributions,
    {
      id: "exit-executed",
      on: exit.executed_on,
      kind: "flow" as const,
      detail: `the exit is executed (${exit.cause})`,
      outside: outside(exit.executed_on),
    },
  ];
}

/** The records this arm states none of, so the timeline says which dates it cannot draw. */
export function statesNone(projection: CandidateProjection): readonly NotStated[] {
  const arm = projection.arm;
  return [arm.at_purchase, arm.distributions, arm.exit_line].filter(isAbsence);
}

function byDate(one: TimelineEvent, other: TimelineEvent): number {
  return one.on === other.on ? one.id.localeCompare(other.id) : one.on.localeCompare(other.on);
}

function remainderEvent(
  outcome: TupleOutcome,
  outside: (on: string) => boolean,
): readonly TimelineEvent[] {
  const mark = remainderOf(outcome);
  if (mark.tag !== "came-home") return [];
  return [
    {
      id: "remainder-arrival",
      on: mark.on,
      kind: "remainder-arrival",
      detail: "what the purchase could not deploy reaches the endpoint",
      outside: outside(mark.on),
    },
  ];
}

/** FR-024: the remainder's own arrival, or the named state saying it never made one. */
export function remainderOf(outcome: TupleOutcome): RemainderMark {
  const remainder = outcome.undeployed;
  if (remainder === null) return { tag: "none" };
  const journey = remainder.journey;
  return journey.tag === "tuple.RemainderCameHome"
    ? { tag: "came-home", on: journey.arrived_on }
    : { tag: "stayed", reason: journey.reason };
}

/** FR-023: one segment per declared wait, in and out, each stated in the days the API sent. */
function segmentsOf(
  projection: CandidateProjection,
  outcome: TupleOutcome,
): readonly LatencySegment[] {
  return [
    {
      id: "latency:in",
      from: outcome.span.start,
      to: projection.purchase.purchased_on,
      days: projection.way_in.latency_days,
      label: "the way in's declared settlement",
    },
    ...projection.releases.map((release) => ({
      id: `latency:out:${release.released_on}`,
      from: release.released_on,
      to: release.arrived_on,
      days: release.way_out.latency_days,
      label: "the way out's declared settlement",
    })),
  ];
}

/**
 * Where a date sits on the axis, as a fraction of the window.
 *
 * Layout, never a figure: it is used for a CSS offset and is rendered nowhere. An event outside
 * the window returns a fraction outside `0..1`, which is how FR-020's *drawn outside it and
 * marked* is reached rather than by clamping.
 */
export function positionOf(on: string, window: Timeline["window"]): number {
  const start = Date.parse(`${window.start}T00:00:00Z`);
  const end = Date.parse(`${window.end}T00:00:00Z`);
  const at = Date.parse(`${on}T00:00:00Z`);
  if (!Number.isFinite(start) || !Number.isFinite(end) || !Number.isFinite(at)) return 0;
  if (end === start) return 0;
  return (at - start) / (end - start);
}
