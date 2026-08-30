# Phase 0 — decisions taken before anything was written

**Feature**: `014-candidates` | **Date**: 2026-08-30 | **Spec**: [spec.md](./spec.md)

No `[NEEDS CLARIFICATION]` was open. What follows are the design decisions the specification
left to the plan, each with the alternative it was taken against — recorded because the
alternative is the one an implementer reaches for first.

## D1 — The candidate is a `Tuple` with the caller's plan position beside it

FR-016 orders by the run plan's position in the caller's sequence and FR-017 says that
position is **recorded on the candidate**; FR-023 says the **key** is the five declared terms
and nothing else. Both hold at once only if the position sits beside the key rather than in
it, so an enumerated candidate is `EnumeratedCandidate(key: Tuple, plan_position: int)`.

*Alternative rejected*: leave the position implicit in the set's order. It reads the input off
the output — the order is *produced by* the position — so a sort that ignored the caller's
sequence would still satisfy an assertion written that way.

## D2 — Which of `CompositionRefused`'s three cases fired is a field on the record, in 004

FR-014a. `Unaskable` is a three-member enum in `core/results/composed.py` and
`CompositionRefused.case` carries it; `compose._refusal` sets it at each of its three sites.
Enumeration matches on the enum and never on `reason`.

*Alternative rejected*: match the reason text here. It is the defect FR-014a names, and it
would put 004's wording inside 014's control flow — a sentence edit in another feature
silently reclassifying a pair from *nothing needs to connect* to *nothing connects*, whose
remedies are opposite.

*Why an enum rather than three records*: `CompositionRefused` is one refusal with three
causes and every existing caller treats it as one type. Splitting it would change 004's
return type at every call site to distinguish something only this caller acts on.

## D3 — The no-candidate column is a tagged union, not a reason string

`PairYieldedNoCandidate.why` is `NothingConnects | NothingNeedsToConnect`. FR-014's
"distinguishable without reading prose" is then a property of the type. `NothingNeedsToConnect`
carries the whole `CompositionRefused`, which is how compose's words reach the report verbatim
(SC-008) without this feature holding a copy of them.

## D4 — Enumeration takes the regime's route set as an argument, and checks it

`compose` documents narrowing to one regime's routes as **the caller's** responsibility
(004 FR-017). This feature is that caller, so it takes `routes` and `regime_id` the way
`compose` does rather than re-deriving the narrowing from transitions and a date.

That is also what makes FR-018's third clause reachable: `routes` and `registries.routes`
arrive independently, so a caller can compose over a set the evaluation does not declare.
Left unchecked it produces one `DeclarationMissing` per candidate — a set of drops that all
say the same thing about the question rather than about any candidate. It is refused as a
whole instead, naming the ids.

## D5 — Two refusal unions, because two of the cases cannot arise from enumeration alone

`enumerate_candidates` returns `CandidateSet | EnumerationRefused`;
`survey` returns `CandidateSurvey | SurveyRefused`, where `SurveyRefused` is
`EnumerationRefused` widened by the two that are about handing the set to `compare` — the
benchmark not being a member of it, and the set spanning two streams when `compare` takes one
amount.

*Alternative rejected*: one union. A caller of `enumerate_candidates` matching exhaustively
would then have to handle two cases that never come back, which is the shape
`resolver._check_composition_owner` already argues against: a guard that cannot fire reads as
protection.

## D6 — Two equal run plans for one instrument refuse the whole enumeration

Not in FR-018's list, and added because it is the one input that breaks FR-009's identity.
Two equal plans for one instrument produce **one** `Tuple` twice; `compare` filters the
benchmark by value, so a repeated member that is the benchmark is filtered twice and
*candidates enumerated = evaluated + dropped* fails by one. A set with a repeated member has
no defined count, so it is refused rather than deduplicated — deduplicating would silently
answer a question with fewer candidates than the caller asked for (FR-021).

## D7 — The drop tally groups by the refusal record's type name

FR-011's grouping key is `type(refusal).__name__`. It is structural — not the `reason` text
SC-022 forbids branching on — and it is one fact in one place: an eighteenth member of the
union groups itself, where a hand-written seventeen-arm `match` would be a second copy of the
union's membership going quietly out of step.

## D8 — The set's provenance is what **enumeration** read, not what evaluation read

FR-024. Enumeration reads two sourced things: the legs of every route it put in a candidate,
and the venue quote of every access entry it considered. Those are merged onto the set and
aged at `as_of` under each source's own declared kind. The outcomes' own marks stay on the
outcomes, where 010 already puts them; merging them onto the set as well would be one fact in
two places, and would make the set's mark unable to say what enumeration itself rested on.

## D9 — The ceiling is a new per-owner declaration, `data/candidates/`

FR-019, on `data/composition/`'s precedent exactly: one file per data root, an `[owner]`
table checked against the streams, no default, a second file refused by name, and
`max_candidates < 1` refused at load. Named in `EXEMPT_DIRS` of the provenance gate with its
reason, because how far a search may run describes the owner and not the world.

**The declared number is 1000**, and the argument is in the file: two orders of magnitude
above the nine the shipped registry yields, and below the 12 168 the spec computes for a
dense seven-venue graph at the same declared bound of three — so the day the registry
densifies, the owner is told that enumeration has stopped being the right primitive instead
of waiting for it.
