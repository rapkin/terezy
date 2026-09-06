# What this screen reads, and how a key is placed

Every path below is served today; nothing here is a request for a new field.

## Reads

| Read | For |
|---|---|
| `GET /api/questions?as_of=` | the declared question ids the picker offers (FR-004, FR-006) |
| `GET /api/questions/{id}?as_of=` | each question's `regime_id` and `declared_in` (FR-004, FR-022) |
| `GET /api/scenarios?as_of=` | the declared scenario ids |
| `GET /api/scenarios/{id}?as_of=` | `regimes[].id`, and `transitions[]` with `is_assumption` and `rationale` (FR-016, FR-018) |
| `GET /api/questions/{id}/answer?as_of=` | one column. One read per distinct `(question id, as_of)`, so two columns naming one question are one read (FR-025) |

The answer read takes `question_id` and `as_of` and nothing else. There is no `scenario_id` on
it, by design, and this screen does not ask for one.

## Placing a key in one column, at one horizon

**Narrow three levels before reading a population.** Each level has a state of its own, and
collapsing them reports a column as emptier than it is.

1. `sections[].outcome` is `CandidateSurvey | SurveyRefused | BenchmarkYieldsNoCandidate`.
   Under `SurveyRefused` the column enumerated nothing here and every key is *this column
   enumerated nothing*, with the served reason. `BenchmarkYieldsNoCandidate` **does** carry
   `enumerated` — deliberately, so a failed benchmark does not report every subject as
   unassessed — so its enumeration is read and only its comparison is absent.
2. a survey's `comparison` is `Comparison | BenchmarkUnavailable`. The outcome list is named
   `ranked` on the first and `scored` on the second, which is not one field under two names but
   two records with no relation, so it is narrowed and never dereferenced blind.
3. `sections[].dominance` is `DominanceResult | DominanceRefused`. Under any of the seven
   refusing members there is **no front in this column at this horizon** — including
   `NoBenchmarkToStandAgainst`, which is what a `BenchmarkUnavailable` comparison produces, and
   `BenchmarkWasWithheld`, which fires beside a *complete* `Comparison` when the hurdle itself
   was withheld. That state is named and its reason rendered; FR-010's union then has one side
   empty, which is a finding and not a blank.

Then, for one key, read top to bottom and stop at the first match. The order is total over
`outcome.enumerated.candidates`, measured 2026-09-07 to leave no key unplaced at any of the
owner's three horizons.

1. absent from `outcome.enumerated.candidates` → **not enumerated in this column**.
2. the outcome carries no comparison — `BenchmarkYieldsNoCandidate` — → **enumerated, and this
   section produced no comparison**, naming the benchmark instrument it could not place (that
   record carries `instrument_id` and `enumerated`, and no reason string). Named here rather
   than left to step 8, for the reason step 5 is named: a state the answer *does* give must not
   fire R1's unknown-population alarm.
3. in the comparison's `refused` → **refused**, with that member's own reason.
4. in **this section's** `arrives_after_horizon` → **withheld from the dominance pass**, with the
   served reason. Per section, never across sections: a key withheld at twelve months and
   evaluated at one month is withheld only at twelve. Measured: `inzhur_miltech` is withheld at
   all three of the owner's horizons, which is why steps 6 and 7 alone are not total.
5. in the comparison's `not_comparable` → **computed, but carrying no rate**, with its reason.
   Empty at all three horizons on the shipped root; listed because step 8 is the alarm for a
   population this screen does *not* know, and a known one arriving there would fire it falsely.
6. in `dominance.non_dominated` → **on the front**.
7. in `dominance.dominated` or `not_placed` → that member's own state, with what it carries.
8. anything left → **the answer places it in no population this screen knows**, named as that
   and never as any of the above. Empty over the shipped root; present so a new population is a
   visible state rather than a silent misclassification (Risk R1).

**Two populations are overlays and are not steps.** `dominance.indistinguishable` says *near
which others* — measured 2026-09-07, its four members at one month are all also in
`non_dominated` or `dominated`. `dominance.incomparable` is a property of a **pair**: it removes
neither candidate from any other pair's verdict, carries `left`/`right` rather than a state for
one member, and 019's own evaluated population is *non-dominated + dominated + not placed*, so a
key can be dominated and incomparable at once. Reading either as a placement would report a
state the answer did not give the key.

## Populations that are not read

`outcome.enumerated.no_candidate` is keyed by `(instrument_id, stream_id, why)` and carries no
five-term key, so it takes no part in a membership comparison; 026 already renders it, folded,
on each answer's own screen.

`outcome.comparison.beats_benchmark`, `ties` and `ranked`'s figures are 026's to render inside a
column. This screen adds a mark beside them; it does not restate them.
