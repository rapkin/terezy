# Research: the declared working-day and public-holiday calendar

**Feature**: `017-working-day-calendar` | **Date**: 2026-08-31

Every question the specification left to the plan, with what decided it. Questions the
specification already settled — enumerated versus generative, the three scope facts, reaching
a calendar by id, record-and-defer for the weekend sites — are settled *there* and are not
re-argued here.

## D1 — Where the module lives: `core/calendars/`, a new package

**Decision**: `src/terezy/core/calendars/working_day.py`.

**Rejected: beside `_is_weekend` in `core/primitives/conventions.py`.** FR-017 leaves that
notion in place, and the Terminology section requires the two to stay visibly apart. One module
holding both would be read as one notion within a week, which is the drift this feature exists
to count rather than to cause.

**Rejected: `core/tax/`.** A civil calendar is not a tax fact, and FR-015 ships no consumer —
putting it under `tax/` would suggest one.

## D2 — A row is representable-and-refused in TOML, unrepresentable in the record

**Decision**: `[[day]]` carries `classification` (a closed set of three) and an explicit
`pre_holiday` boolean; the core carries a two-member union where only the working member has a
`pre_holiday` field.

This is what lets SC-004's *a pre-holiday day on a non-working date* be a load failure naming
the file and the date, while the Key Entities line — "a pre-holiday non-working day is
unrepresentable rather than refused at the query" — holds inside the core. A shape that made it
unrepresentable in TOML too would have nothing for SC-004's case to write.

`pre_holiday` is required on every row rather than defaulting to `false`, on
`OfficialRateFile.observation`'s rule: a forgotten line and a deliberate *no* must not look
alike (FR-007).

## D3 — Provenance sits on the row, the week, and the coverage window

**Decision**: three citation sites, not one and not per file.

FR-005 puts provenance per row and gives the argument. Two declaration elements are not rows
and still assert something a source has to vouch for:

* **the week** — which weekdays the law makes rest days, and where its week starts. This is
  what `conventions._is_weekend` asserts with no citation at all;
* **the coverage window** — the claim that somebody read this jurisdiction's law for these
  dates.

The window's citation is also the only home an **empty enumeration** has. A year whose holiday
regime was suspended declares no rows, so per-row provenance gives the suspending act nowhere
to be cited from; the window is the declaration that year's emptiness belongs to.

## D4 — Weekday names in code are not domain knowledge

**Decision**: a seven-entry mapping from `monday` … `sunday` to `date.weekday()` indices lives
in the module, uncited.

It names the days of the week; it does not say which of them a jurisdiction rests on. The
uncited fact FR-002 is about is *which* — and that is declared, cited, per calendar.

## D5 — Scope is checked where the question is asked

**Decision**: every query takes the scope it requires; the mismatch is produced by the query.
FR-003b, and it is what makes the check reachable in a feature that ships no consumer.

## D6 — A query takes the mapping and the id, never a calendar it found itself

**Decision**: `classify(calendars, calendar_id, *, scope, on_date)`.

Satisfies FR-003a (named, never selected by jurisdiction or load order) and FR-016 (every date
and every calendar an argument) in one signature. `CalendarNotDeclared` is what an id absent
from the mapping produces.

## D7 — A week inside the window with no working day is refused at load

**Decision**: `working_day.week_without_a_working_day` finds the first such week and the
loader refuses on it, naming the file and that week's first date. The reasoning is in the
core, beside the queries whose totality depends on it; the file name is all the data boundary
adds.

The specification refuses a rest pattern naming all seven weekdays at load, with the reason:
*a calendar with no working days answers every working-day question with a refusal that names
the date rather than the declaration, sending the reader to fix the wrong thing.* Seven
consecutive enumerated non-working rows reach the identical state by another road, and FR-011
fixes the refusal union at exactly three reasons — none of which is *this week has no working
day*. Refusing at load keeps FR-014's answer total and sends the reader to the declaration.

Weeks that straddle a window end are excluded, because FR-014 already refuses those at the
query with the ran-off-an-end discriminator.

## D8 — FR-018's scan counts modules, and counts the registry path

**Decision**: `tests/contract/test_no_calendar_free_working_day.py`, parsing `src/` with `ast`.

A site counts when a module **calls** `is_business_day` or **calls** `business_day_rule` —
the second is the registry path, and the specification is explicit that narrowing to the first
would pass while asserting something false, because `year.py::_due_on` is counted and reaches
it that way.

**A mention is deliberately not a call.** `loader.py` names `BUSINESS_DAY_FNS` to validate a
declared name against it and `canonical.py` reads a `business_day_rule` string off a record;
neither decides anything about a date. Counting references would put both in the set and make
the assertion false — which is the mirror of the narrowing the specification warns about, and
was found by running it.

The holiday-literal half searches for `date(y, m, d)` constructions and `(month, day)` pairs
whose month-and-day matches a public holiday. **The list of holiday month-and-days lives in the
test**, which is where the searched-for thing belongs; it is not a value the engine holds. Its
limits are measured and recorded in the module docstring rather than claimed.

## D9 — The shipped Ukrainian calendar, and why its enumeration is empty

**Decision**: one shipped calendar, `ua_civil`, scope `civil`, window **2025-01-01 … 2026-10-30**,
week = `["sunday"]` starting Monday, `day = []`.

Retrieved 2026-08-31 by `curl --compressed -A '<browser UA>'` against
`zakon.rada.gov.ua/laws/show/<id>/print` — **both** the browser user-agent and `/print` are
required, and the record of the 2026-08-30 failure in the specification's owner verification
task 1 is now closed. Four transcriptions, no readings beyond them:

1. **ст. 73 КЗпП** carries the amendment marker *«У період дії воєнного стану не застосовуються
   норми статті 73 згідно із Законом № 2136-IX від 15.03.2022 з урахуванням змін, внесених
   Законом № 2352-IX від 01.07.2022»*. The holiday list is not applied.
2. **ст. 53 КЗпП** carries the identical marker. The pre-holiday shortened day is not applied.
3. **ст. 67 ч. 3 КЗпП** — moving a rest day off a holiday — carries it too.
4. **ст. 67 ч. 2 КЗпП** — *«Загальним вихідним днем є неділя»* — is **not** suspended.

So inside the window the law enumerates no holidays and no pre-holiday days, and makes exactly
one weekday a rest day. **The enumeration is empty and means it** (spec, Edge Cases).

**Why the window starts 2025-01-01**: every amendment touching these three articles predates it
(№ 3258-IX від 14.07.2023 for ст. 73, № 3494-IX від 22.11.2023 for ст. 67), so the consolidated
text retrieved today is the text in force throughout. **Why it ends 2026-10-30**: martial law is
in force continuously from 2022-02-24 through 05:30 on 2026-10-31 by the extension chain
recorded on Указ № 64/2022, the last being Указ № 596/2026 від 13.07.2026 — 90 діб from 05:30 on
2026-08-02. 2026-10-30 is the last day that chain covers whole. A date past it refuses (FR-010),
which is the loud staleness the enumerated form was chosen for.

**Why the week is Sunday and not Saturday-and-Sunday.** ст. 67 ч. 2 makes *Sunday* the general
rest day and puts the second rest day of a five-day week in the enterprise's own schedule —
*«якщо він не визначений законодавством, визначається графіком роботи підприємства»*. A
jurisdiction's civil calendar transcribes what the jurisdiction's law says; Saturday would need
a source that says it, and there is none. This is precisely the fact FR-002 predicted would be
inherited from the implementer, and `conventions._is_weekend` asserts it today with no citation.
**Owner verification task 3** records the divergence. Nothing consumes either notion, so no
figure moves (SC-010).

## D10 — What was measured rather than supposed

* **FR-006, FR-006a, FR-006b are satisfied on `main`.** `_has_observed_value` counts dates as
  well as numbers, so a `[[day]]` row — a date and a label, no number — is a sourced table. The
  delta measurement SC-005 asks for is performed against a real calendar file in
  `tests/contract/test_provenance_gate.py`.
* **SC-013's first half is already satisfied on `main`**: `specs/features.toml`'s
  `martial-law-ends-one-belief-two-places` names the calendar as the third instance. This
  feature verifies it and adds no mechanism.
