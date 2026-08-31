# Data model: the working-day calendar

**Feature**: `017-working-day-calendar` | **Date**: 2026-08-31

## The declared file — `data/calendars/<id>.toml`

```toml
[calendar]
id           = "ua_civil"
jurisdiction = "UA"
authority    = "Верховна Рада України"
scope        = "civil"          # civil | settlement

[calendar.coverage]
first        = "2025-01-01"
last         = "2026-10-30"
kind         = "tax_rule"
source       = "…"
retrieved_on = "2026-08-31"
verified_on  = ""

[calendar.week]
rest_days    = ["sunday"]       # non-empty, never all seven, never defaulted
starts_on    = "monday"
kind         = "tax_rule"
source       = "…"
retrieved_on = "2026-08-31"
verified_on  = ""

day = []                        # written explicitly; an omitted key is a load failure

# [[day]]
# on_date        = "2026-01-01"
# classification = "public_holiday"   # public_holiday | rest_day | working_day
# pre_holiday    = false              # required; true only on a working classification
# kind           = "tax_rule"
# source         = "…"
# retrieved_on   = "…"
# verified_on    = ""
```

`data/calendars/` joins `SOURCED_DIRS` in `scripts/check_provenance.py`. Every table above
carries a date leaf outside `STRUCTURAL_KEYS`, so the gate requires the citation and the
observation kind on each of the three — which is the hole `e6def2f` closed.

## The core records — `terezy.core.calendars.working_day`

| Record | Fields |
|---|---|
| `CalendarScope` | `Enum`, exactly two: `CIVIL`, `SETTLEMENT` (FR-003) |
| `DecidedBy` | `Enum`, exactly three: `REST_PATTERN`, `ENUMERATED_NON_WORKING_DAY`, `DECLARED_MOVE` (FR-012) |
| `DeclaredWeek` | `rest_days: frozenset[int]`, `starts_on: int`, `provenance` |
| `WorkingDay` | `on_date`, `decided_by`, `pre_holiday: bool`, `provenance` |
| `NonWorkingDay` | `on_date`, `decided_by`, `provenance` |
| `DayClassification` | `WorkingDay \| NonWorkingDay` |
| `WorkingDayCalendar` | `id`, `jurisdiction`, `authority`, `scope`, `covers: tuple[date, date]`, `week: DeclaredWeek`, `rows: tuple[DayClassification, ...]` |

Weekdays are `date.weekday()` indices — Monday 0 … Sunday 6 — throughout. `rows` is strictly
ascending by `on_date` and looked up by bisection, exactly as `OfficialRateSeries.observations`
is.

**`pre_holiday` exists only on `WorkingDay`.** That is the whole of FR-012's *"the answer MUST
make a wrong state unrepresentable"*: there is no field for a pre-holiday non-working day, so
the case SC-004 writes into a file cannot survive the load.

## The refusal — `CalendarUnavailable`, exactly three members (FR-011)

| Member | Carries |
|---|---|
| `CalendarNotDeclared` | `wanted_id`, `reason`. **No window** — nothing was found to have one. |
| `CalendarScopeMismatch` | `calendar_id`, `scope_wanted`, `scope_found`, `reason` |
| `CalendarOutOfCoverage` | `calendar_id`, `on_date`, `covers`, `missed: Missed`, `reason` |

`Missed` is `BEFORE_WINDOW`, `AFTER_WINDOW`, `RAN_OFF_AN_END` — the discriminator FR-011's third
reason requires, not a fourth reason. There is deliberately no member for *this jurisdiction has
no calendar*: FR-003a means nothing can ask, so shipping one would be a guard whose message is
false.

## The queries (FR-012 – FR-014)

```python
classify(calendars, calendar_id, *, scope, on_date)                    -> DayClassification | CalendarUnavailable
first_working_day_on_or_after(calendars, calendar_id, *, scope, on_date) -> WorkingDay | CalendarUnavailable
last_working_day_on_or_before(calendars, calendar_id, *, scope, on_date) -> WorkingDay | CalendarUnavailable
last_working_day_of_week(calendars, calendar_id, *, scope, on_date)      -> WorkingDay | CalendarUnavailable
```

`calendars: Mapping[str, WorkingDayCalendar]`. Four arguments, no module state, no clock
(FR-016).

## Load-time refusals (FR-007, SC-004)

Unknown field · missing required field · missing coverage window · window running backwards ·
missing or empty `rest_days` · `rest_days` naming all seven weekdays · an unrecognised weekday
name · missing `starts_on` · two rows for one date · rows out of order · a row dated outside the
window · `pre_holiday = true` on a non-working classification · an unrecognised `classification`
· an unrecognised `scope` · a week lying wholly inside the window with no working day in it
(D7) · an undeclared observation kind (resolver) · two files declaring one calendar id
(resolver).
