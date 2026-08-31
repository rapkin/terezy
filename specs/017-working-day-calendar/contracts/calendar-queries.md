# Contract: what a consumer may ask a calendar

**Feature**: `017-working-day-calendar`

The whole exposed surface (FR-015). Nothing else is public, and nothing in `src/` calls any of
it — this feature ships **no consumer**.

## Preconditions every query shares

1. The calendar is reached by **naming its declared id** in `calendars`. An id that is not a key
   returns `CalendarNotDeclared(wanted_id=…)`. Nothing is selected by jurisdiction, by scope, or
   by load order (FR-003a).
2. The caller states the **scope its question requires**. A calendar whose scope differs returns
   `CalendarScopeMismatch(scope_wanted=…, scope_found=…)`. **No computation differs by scope**
   (FR-003).
3. Every date is an **argument**. No clock, no `as_of`, no module-held calendar (FR-016).

## `classify(…, on_date) -> DayClassification | CalendarUnavailable`

Returns `WorkingDay` or `NonWorkingDay`, each stating `decided_by`:

| `decided_by` | When |
|---|---|
| `REST_PATTERN` | no row mentions the date; the declared `rest_days` decided it |
| `ENUMERATED_NON_WORKING_DAY` | a row declares `classification = "public_holiday"` |
| `DECLARED_MOVE` | a row declares `"rest_day"` or `"working_day"` |

Provenance on the answer is the deciding declaration's own — the row's, or the week's where the
pattern decided it. An empty `verified_on` therefore marks every answer derived from it (SC-005).

`on_date` outside `covers` returns `CalendarOutOfCoverage` with `BEFORE_WINDOW` or
`AFTER_WINDOW`. The rest pattern is never extended past either end (FR-010).

## `first_working_day_on_or_after` / `last_working_day_on_or_before`

Skips every consecutive non-working day. A search that would leave `covers` returns
`CalendarOutOfCoverage` with `RAN_OFF_AN_END` — never the window's edge, never a loop (FR-013).
The discriminator separates *the date you asked about was never covered* from *the date you
asked about was covered and the answer is not*: only the second is fixed by extending the
calendar.

## `last_working_day_of_week`

The last working day of the week **containing** `on_date`, where the week runs seven days from
the calendar's own declared `starts_on` (FR-014). A week either of whose ends lies outside
`covers` returns `CalendarOutOfCoverage` with `RAN_OFF_AN_END` **even when a working day exists
inside the window** — answering from the visible part would return a plausible date that is not
the answer to the question asked.

A week lying wholly inside the window always has a working day, because the loader refuses a
calendar where one does not (research D7). So this query is total on the window.
