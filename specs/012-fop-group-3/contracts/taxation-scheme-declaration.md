# Contract: the taxation-scheme and crediting-destination declarations

**Feature**: `012-fop-group-3`. The record shapes are
[data-model.md](../data-model.md) §1, §3 and §7; this file is the **file-level contract** —
what a declaration must satisfy to load, and what it gets refused for. Every refusal names
the file and the field path in the file's own notation, per `data/README.md` rule 1.

## `data/tax/schemes/<id>.toml` — one scheme per file

### Required, no defaults

| Key | Rule |
|---|---|
| `scheme.id` | unique across `data/tax/schemes/`; a collision names **both** files |
| `scheme.name` | non-empty |
| `scheme.jurisdiction` | non-empty; the jurisdiction whose tax currency the base is struck in |
| `scheme.tax_currency` | a declared currency code |
| `scheme.variant` | non-empty — which of the law's alternative rate sets this file declares (FR-002). A scheme with one variant still names it |
| `scheme.reporting_cadence` | non-empty (FR-004). Declared and **unused**: this feature records a liability against the period it accrues to and models no payment timing |
| `scheme.declared_for` | `"stream"` or `"reading"`. A `"reading"` scheme may not be named by an income stream (FR-010a, FR-026) |

At least one `[[scheme.rate_component]]` or `[[scheme.periodic_component]]`. A scheme that
charges nothing at all is a file nobody meant to write.

### A rate component

`id` unique within the scheme, `name` non-empty and **the name the law uses** (FR-006).
At least one `[[scheme.rate_component.rate]]`, and every entry carries:

`effective_from` (ISO date), `rate_pct` (≥ 0), `note`, `kind`, `source`, `retrieved_on`,
`verified_on` (present, may be empty).

Entries are read **in the order they are written** and are never sorted. Refused:

- an empty schedule
- an `effective_from` equal to the previous entry's — two entries on one date
- an `effective_from` before the previous entry's — the file's order disagrees with its dates
- a negative `rate_pct` — a refund, which no source here declares

`rate_pct` is divided by 100 exactly once, at the loader, after the non-negative check, so
the error quotes the percentage the file wrote.

### A periodic component

As above, with `period = "month"` (a closed set) and
`[[scheme.periodic_component.amount]]` entries carrying `amount` (≥ 0) and `currency` in
place of `rate_pct`. **An amount is not a rate and may not be written as one**: there is no
`rate_pct` key on a periodic component and no `amount` key on a rate component, so the
confusion FR-019 forbids cannot be spelled.

### Recorded context

`[[scheme.rate_component.context]]` and `[[scheme.periodic_component.context]]` are optional
and repeatable. Each carries `id`, `statement`, `not_applied_because` and its own provenance.

This is where a **cited fact that is deliberately not applied** lives (FR-008a). It is a
declaration, not a comment, for one reason: a comment cannot be rendered on the figure that
the fact does not move, and a schedule that declares a commencement and nothing else asserts
a permanent charge. `not_applied_because` is required so the omission can never be read as an
oversight.

## `data/tax/destinations/<jurisdiction>.toml` — the normative table

One `[[destination]]` per `(scheme, venue)` pair. A second row for the same pair names both
files.

| Key | Rule |
|---|---|
| `scheme` | resolves to a declared scheme |
| `venue` | resolves to a declared venue in `data/venues.toml` |
| `verdict` | `"interpreted"` or `"unsettled"` |
| `grounds` | non-empty — the row's recorded judgement, which is what makes the table normative rather than illustrative |
| `resolution_path` | non-empty — what closes the question |
| provenance | `kind`, `source`, `retrieved_on`, `verified_on` on the row itself |

At least one `[[destination.reading]]`, each carrying `id` (unique within the row), `label`,
its own provenance, and **exactly one** of:

- `scheme` — a declared scheme, plus `recognised_on`, a **declared date name**. The name is a
  string the engine never compares against a literal; the caller supplies a mapping from
  names to dates, and a reading whose name the caller did not supply refuses by name rather
  than falling back to another date.
- `uncomputable_because` — a candidate that is named on the switch and not computed, with the
  reason in its own words (Line 3's second sentence). Declaring the reason rather than
  pointing at an undeclared scheme is what keeps *an unresolvable reference fails at load*
  intact for every other reference in the repository.

`departs_from_source` is optional: where this system deliberately computes something other
than what the cited source computes, the divergence is declared here and rendered **on the
figure** (SC-017a).

`verdict = "interpreted"` requires **exactly one** reading and it must be computable — an
INTERPRETED row is a charge, and a charge with no candidate is a contradiction.
`verdict = "unsettled"` requires at least one reading and a non-empty `resolution_path`.

## `data/streams/<owner>.toml`

`income_tax_rate_pct` is **removed from the schema**. Because the stream table forbids extra
keys, a file still carrying it fails at load naming the key — the migration announcing itself
rather than ignoring a rate the owner may believe is being applied.

| Key | Rule |
|---|---|
| `credited_to` | **required**, a declared venue. The tax event's location |
| `tax_scheme` | optional; a declared scheme whose `declared_for` is `"stream"`. Omitted means the owner has named none, which is not a treatment charging zero |

`arrives_at` and `credited_to` are two facts and neither is defaulted from the other, in
either direction (FR-024a). `arrives_at` is the **routing origin** — the venue every funding
route starts from. `credited_to` is where the income is credited for the purpose of deciding
which reading applies. For the owner today they hold different values.

A stream naming a scheme no file declares fails at load naming the file, the stream and the
unknown treatment (FR-017). A stream naming a **venue** the destinations table has no row for
does **not** fail at load: that is FR-027's refusal, produced when the charge is attempted,
and making it a load failure would put the destination beyond the reach of the requirement
that exists to name it.

## What the provenance gate then requires

`data/tax/schemes/` and `data/tax/destinations/` are under `data/tax/`, which
`scripts/check_provenance.py` already walks with `rglob`. Every table carrying a numeric leaf
— a rate entry, an amount entry — must therefore carry `kind`, `source`, `retrieved_on` and a
present `verified_on`, and `kind` must name a threshold declared in
`data/observation_kinds.toml`. Every value in this feature is stamped `tax_rule`.

A destination row and a reading carry **no numeric leaf**, so the gate does not demand their
citations — the loader does, because FR-026 requires each figure to carry its reading's own
citations and a reading with none could not satisfy it. That is the same reading
`non_publication_rule` takes in feature 011.
