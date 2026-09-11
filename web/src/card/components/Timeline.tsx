/**
 * FR-020 to FR-024: when it happened, on the horizon's own axis.
 *
 * A list rather than a picture, with the position carried as a CSS offset beside it. Half of
 * *why this figure* is *over what period*, and a timeline a reader cannot read as text has
 * answered neither half (FR-029).
 */
import type { CandidateProjection, TupleOutcome } from "@/api/shapes";
import { positionOf, statesNone, timelineOf, type TimelineEvent } from "@/card/events";
import { count, day } from "@/design/format";
import { Badge } from "@/components/ui/badge";

export function Timeline({
  projection,
  outcome,
}: {
  projection: CandidateProjection;
  outcome: TupleOutcome;
}) {
  const timeline = timelineOf(projection, outcome);
  return (
    <section className="space-y-3" data-timeline aria-label="when it happened">
      <h3 className="text-sm font-semibold">when it happened</h3>
      <p className="text-xs text-[var(--ink-muted)]" data-window={`${timeline.window.start}/${timeline.window.end}`}>
        the horizon runs {day(timeline.window.start)} to {day(timeline.window.end)}
      </p>
      <ol className="space-y-1">
        {timeline.events.map((event) => (
          <li
            key={event.id}
            data-event={event.id}
            data-event-kind={event.kind}
            data-outside={event.outside ? "yes" : "no"}
            className="flex flex-wrap items-baseline gap-2 text-xs"
            style={{ marginInlineStart: `${String(offset(event, timeline.window))}%` }}
          >
            <span className="font-mono">{day(event.on)}</span>
            <span>{event.detail}</span>
            <Outside event={event} />
          </li>
        ))}
      </ol>

      <ul className="space-y-1" data-latency>
        {timeline.segments.map((segment) => (
          <li key={segment.id} data-segment={segment.id} className="text-xs">
            <span className="text-[var(--ink-muted)]">{segment.label}: </span>
            {day(segment.from)} to {day(segment.to)}, {count(segment.days)} day(s) of waiting —
            inside the span the rate is measured over
          </li>
        ))}
      </ul>

      <Remainder remainder={timeline.remainder} />
      <StatesNone projection={projection} />
    </section>
  );
}

/**
 * The event's place on the axis, as a percentage of the window.
 *
 * Layout and not a figure: it is an indent, it is never rendered as a number, and an event
 * outside the window keeps the indent inside the page rather than being clamped on the axis —
 * the **claim** that it fell outside is the badge beside it, in text.
 */
function offset(event: TimelineEvent, window: { start: string; end: string }): number {
  const at = positionOf(event.on, window);
  return Math.min(Math.max(at, 0), 1) * 60;
}

function Outside({ event }: { event: TimelineEvent }) {
  if (!event.outside) return null;
  return (
    <Badge tone="warn" data-outside-window={event.id}>
      outside the horizon window
    </Badge>
  );
}

/**
 * FR-007: the dated records this arm states none of, named rather than left out.
 *
 * A fund declares a record date and an execution date its ledger does not carry; a bond and a
 * balance declare neither. A timeline that simply drew fewer markers would leave a reader unable
 * to tell *this arm has no such date* from *the engine reported nothing*.
 */
function StatesNone({ projection }: { projection: CandidateProjection }) {
  const absent = statesNone(projection);
  if (absent.length === 0) return null;
  return (
    <ul className="space-y-1" data-states-none>
      {absent.map((state) => (
        <li key={state.what} role="note" data-not-stated={state.what} className="text-xs">
          no <strong>{state.what}</strong> on the {state.arm} arm — {state.reason}
        </li>
      ))}
    </ul>
  );
}

/** FR-024: the remainder's own arrival, or the named state saying it never made one. */
function Remainder({ remainder }: { remainder: ReturnType<typeof timelineOf>["remainder"] }) {
  switch (remainder.tag) {
    case "none":
      return (
        <p className="text-xs text-[var(--ink-muted)]" data-remainder-mark="none">
          the purchase deployed the whole of what arrived, so nothing was left to come home
        </p>
      );
    case "came-home":
      return (
        <p className="text-xs" data-remainder-mark="came-home">
          what the purchase could not deploy reached the endpoint on {day(remainder.on)}
        </p>
      );
    case "stayed":
      return (
        <p className="text-xs" role="note" data-remainder-mark="stayed">
          what the purchase could not deploy never came home: {remainder.reason}
        </p>
      );
  }
}
