# Tasks: The declared working-day and public-holiday calendar

**Feature**: `017-working-day-calendar` | **Date**: 2026-08-31

Ordered by dependency. `[P]` marks tasks that touch disjoint files and may run together.
Every test is written before the module it imports, and fails with `ImportError` until that
module exists — which counts (specs/README.md step 2).

## Phase 0 — the two things worth landing on their own

- [x] **T001** `tests/contract/test_no_calendar_free_working_day.py`: FR-018's scan. Parse every
  module under `src/` with `ast`. A module counts as deciding a working day without a declared
  calendar when it calls `is_business_day`, calls `business_day_rule`, or names
  `BUSINESS_DAY_FNS`. Assert the set is **exactly** `fixed_income.py`, `fund.py`, `year.py` —
  plus `conventions.py` itself, which declares the notion rather than consuming it. Assert
  separately that the registry path is what puts two of them there, so a scan narrowed to direct
  callers fails this file rather than passing it (SC-009). Second half: no `date(y, m, d)`
  construction or `(month, day)` literal in `src/` matches a public-holiday month-and-day; the
  searched-for list lives in the test. Record the scan's measured limits in the module docstring.
- [x] **T002** FR-017a: correct the three sentences that go false.
  `core/primitives/conventions.py::_is_weekend` and `core/instruments/fund.py::settlement_date`
  each promise behaviour *"until that data exists"* — the data exists and neither site consults
  it. `core/primitives/conventions.py::is_business_day` predicts that one function changes and
  every settlement date changes with it — this is that day and it did not. Each correction says
  what is true instead: a calendar is declarable, these sites do not consult one, by CL-1,
  2026-08-30. Name symbols, not line spans.
- [x] **T003** Checkpoint: gates green, commit.

## Phase 1 — the core records and the four questions

- [x] **T004** `tests/unit/test_working_day_calendar.py`, part 1: construct all three refusal
  members and assert them **field by field**, never by matching a message (SC-003) —
  `CalendarNotDeclared` carries an id and no window; `CalendarScopeMismatch` carries both scopes;
  `CalendarOutOfCoverage` carries the window and a `Missed` discriminator separating before,
  after and ran-off-an-end. Assert `CalendarScope` has exactly two members and
  `CalendarUnavailable` exactly three, and that no member exists for a jurisdiction having no
  calendar.
- [x] **T005** `src/terezy/core/calendars/__init__.py` and `working_day.py`: the records and
  refusals of [data-model.md](./data-model.md). `pre_holiday` on `WorkingDay` only.
- [x] **T006** `tests/worked_examples/test_working_day_classification.py`: a synthetic calendar —
  a fortnight, two declared holidays, one pre-holiday working day, one moved working day — with a
  hand-written date-by-date table checked in beside the assertions (SC-001). Each row asserts the
  classification **and** `decided_by` **and** `pre_holiday`.
- [x] **T007** `working_day.classify`: bisect the rows, fall through to the declared rest pattern,
  and carry the deciding declaration's provenance onto the answer.
- [x] **T008** `tests/unit/test_working_day_calendar.py`, part 2: the FR-012–FR-014 battery over a
  week containing a holiday, a pre-holiday day and a moved working day, against a hand-written
  table, with no rate series and no money anywhere in the file (SC-008). Include User Story 3's
  four mapping rows by name.
- [x] **T009** `first_working_day_on_or_after`, `last_working_day_on_or_before`,
  `last_working_day_of_week`.
- [x] **T010** `tests/unit/test_working_day_calendar.py`, part 3: SC-002's out-of-window battery —
  a date before the window, a date after it, a next-working-day search that runs off the end, and
  a last-working-day-of-week search whose week straddles the boundary. All four typed refusals,
  zero classifications, and a scan asserting no keyword argument or module constant turns any of
  them into an answer.
- [x] **T011** Checkpoint: gates green, commit.

## Phase 2 — the declaration surface

- [x] **T012** `tests/contract/test_calendar_declaration_loading.py`: SC-004's battery, every case
  writing a real TOML file and asserting the `DeclarationError` names the file **and** the
  offending field or date. Cases: unknown field · missing field · missing window · window running
  backwards · missing `rest_days` · empty `rest_days` · `rest_days` naming all seven weekdays ·
  an unrecognised weekday · missing `starts_on` · an unrecognised `scope` · an unrecognised
  `classification` · two rows for one date · rows out of order · a row outside the window ·
  `pre_holiday = true` on a non-working row · a week wholly inside the window with no working day
  · an undeclared observation kind · two files declaring one id. Assert no case substitutes a
  default.
- [x] **T013** `schema.py`: `CalendarFile`, `CalendarTable`, `CalendarCoverageTable`,
  `CalendarWeekTable`, `CalendarDayTable`, all `STRICT`, all fields required.
- [x] **T014** `loader.py`: `working_day_calendar_from_file`, and the `CALENDAR_*` field-path
  constants beside it.
- [x] **T015** `resolver.py`: `CALENDARS_DIR`, `working_day_calendars_from_data_root(root, kinds)`
  — id collision across files, and the observation-kind check over every citation on a loaded
  calendar, on `official_rates_from_data_root`'s precedent for a numberless table.
- [x] **T016** `scripts/check_provenance.py`: `data/calendars/` joins `SOURCED_DIRS`, with its
  reason written where the others are.
- [x] **T017** Checkpoint: gates green, commit.

## Phase 3 — the shipped calendar, and the gate measured on it

- [x] **T018** `data/calendars/ua_civil.toml`: the one shipped `civil` calendar. Window
  2025-01-01 … 2026-10-30, `rest_days = ["sunday"]`, `starts_on = "monday"`, `day = []`. Three
  citation sites, each quoting the provision it transcribes, each `verified_on = ""`. The file's
  header states why the enumeration is empty and why the window ends where it does, and does not
  restate the specification.
- [x] **T019** `tests/contract/test_provenance_gate.py`: SC-005's **measured delta**. Record the
  gate's full finding set over a scratch data root; add a calendar file carrying a real row;
  record it again and assert the difference is exactly that row's lines; delete the row's
  `source` and assert the gate errors on it. A widening and a narrowing are both visible in a
  difference; neither is in a single assertion that one case now fails.
- [x] **T020** Checkpoint: gates green, commit.

## Phase 4 — the data-only claims, the no-consumer claim, and the documentation

- [x] **T021** `tests/contract/test_calendar_data_only.py`: SC-006 — a second jurisdiction's
  calendar with a different rest pattern and a different week start, declared purely as data in a
  scratch root, loads, is addressable, classifies by *its* pattern, and leaves the first's answers
  unchanged, with zero source lines changed. SC-007 — a consumer asking for `civil` and handed a
  `settlement` calendar refuses naming both scopes. SC-011 — a scan asserting no calendar is
  reachable except through an argument: no module-level `WorkingDayCalendar`, and no query with a
  default for its `calendars` or `on_date` parameter.
- [x] **T022** SC-010: assert the golden suite is untouched by this feature, and that nothing in
  `src/` outside `core/calendars/` and the declaration layer imports `core.calendars`.
- [x] **T023** `docs/METHODOLOGY.md`: a new `## 35. The working-day calendar` **before** `##
  35. Where to look next`, which becomes `## 36`. What a working day, a rest day, a public
  holiday and a pre-holiday day mean here; how the declared pattern and the enumerated exceptions
  combine; what happens past the window (FR-021, SC-012). Run `scripts/check_methodology_refs.py`.
- [x] **T024** `docs/REQUIRED_TESTS.md`: this feature's rows and what they do and do not close —
  H1 exercised not closed, H2 exercised, E8 not attempted.
- [x] **T025** Verify SC-013 on this branch: `specs/features.toml`'s
  `martial-law-ends-one-belief-two-places` already names the calendar as the third instance, and
  no declaration, field or record introduced here is keyed to martial law ending. Report it
  verified rather than re-writing it. Add the closing of owner verification task 1 and the new
  task 3 to `spec.md`'s owner verification section.
- [x] **T026** Final gates, `/condense`, `/code-review`, iterate to clean.

T025's SC-013 check came back **already satisfied on `main`**: `specs/features.toml`'s
`martial-law-ends-one-belief-two-places` names the calendar as the third instance, so this
branch adds nothing to it. Nothing declared here is keyed to martial law ending — the coverage
window ends on a **date**, and the reason that date is where it is lives in the citation.
