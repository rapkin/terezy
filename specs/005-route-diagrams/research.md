# Phase 0 research: route diagrams

**Feature**: `005-route-diagrams` | **Date**: 2026-08-23 | **Spec**: [spec.md](./spec.md)

Both clarifications were resolved by the owner on 2026-08-22 and one gap (FR-022) was
closed by external review, so nothing here is a `NEEDS CLARIFICATION`. The decisions below
are what the plan rests on.

---

## D1 — The renderer lives in `api`, and the core never learns to format

**Decision.** `src/terezy/api/diagrams/`, a package of free functions consuming the same
declared records and result types everything else consumes.

**Rationale.** FR-020, and Principle III mechanically: `.importlinter` forbids `core` from
importing anything that formats, and the reason is that a core which can render is a core
that can be asked to round. Rendering is presentation, one layer up, reading the same
records — **no parallel data model and no second reading of the declaration files**, which
is the other half of FR-020 and the thing that would let a diagram drift from the numbers.

**Alternatives rejected.** A `core/diagrams/`: forbidden, and rightly. A standalone script
holding the logic: FR-021 wants the script to be a thin printer over a tested library, not
the library itself.

## D2 — One number-rendering rule, in one module, and a test that no second one exists

**Decision.** `api/diagrams/numbers.py` defines the project's only diagram-label number
rule: a percentage as a fixed two-decimal value with `%`, an amount as a fixed two-decimal
value with its currency code. Every figure on every diagram goes through it.

**Rationale.** FR-022. The review found the real gap: results carry floats, the project's
canonical float form is unreadable hexadecimal, and no human-readable decimal rule existed —
so "the diagram shows the result's figure" was undefined as written. Two decimals is an
implementer choice the spec explicitly leaves open; **singularity is not**. The rule is
modelled on the single project tolerance: defined once, imported everywhere, and a second
one is a defect rather than a preference.

**The rule rounds, and the diagram is therefore not the audit trail.** FR-008 permits
exactly this one transformation and no other. Say it in the module docstring, because the
next person will otherwise reach for three decimals at one call site and call it a fix.

**Enforced, not asked for.** A contract test greps the diagram package for inline float
formatting — `:.2f`, `format(`, `round(` — and fails on any outside `numbers.py`.

## D3 — Node identity is positional; the human name lives only in the quoted label

**Decision.** A node's Mermaid id is `n<k>`, where `k` is the entity's position in a sorted
list of the entities being drawn. The declared name and id go in the quoted, escaped label.

**Rationale.** FR-017 and FR-018 pull in opposite directions if the Mermaid id is derived
from the declared id. Sanitising `binance-p2p` and `binance_p2p` into a safe identifier
collapses two distinct venues into one node — distinct entities silently merged, which is
FR-018 violated and invisible in the output. A positional id is injective by construction,
immune to every hostile character in SC-008's battery, and deterministic because the list is
sorted (FR-016).

**The cost, stated:** the raw Mermaid text is less readable to a human reading the source.
That is the right trade — the diagram is meant to be rendered, and correctness of identity
beats legibility of the intermediate form.

## D4 — Marks are label text; styling may only add emphasis, never carry meaning

**Decision.** Unverified, stale and synthetic marks are rendered as visible tokens inside
the label text. Mermaid `classDef` styling may be added on top, never instead.

**Rationale.** FR-015: every mark must survive rendering. A mark carried only by a colour
class is lost the moment the text is pasted into a tool with a different theme, diffed, or
read as source in a golden file — and the golden files are one of exactly two places this
output lands (FR-021). SC-004's six mark states are asserted against the text with all
styling stripped, which is the test that keeps this honest.

## D5 — Two modes, named on the diagram, and a computed cost on neither

**Decision.** `Mode` is a closed enum: `TOPOLOGY` and `DECLARED_FIGURES`. The mode's name is
rendered in the diagram itself. A computed ramp cost never appears on a registry graph in
either mode.

**Rationale.** FR-006 in full. The mode on the face of the diagram is what stops a
numberless picture being read as "zero fees" — the same class of error as an unlabelled
one-way figure. And a computed cost exists only per `(destination × stream × route)`, which
a registry graph does not name: putting one there is 002's FR-008 violated in picture form,
which is why it is forbidden in the mode that shows numbers too, not only in the other one.

## D6 — The graph is derived from declarations, not from feature 003's report

**Decision.** FR-005's *no exit declared* mark is computed here, from the declarations, by
asking whether any declared exit route leaves that destination. `core/routes/coverage.py` is
not imported.

**Rationale.** The spec says in as many words that the two parallel features are
deliberately not depended on. Reading 003's report would make a picture depend on an audit,
couple two features landing in parallel, and — because 003's verdicts are per regime and
advisory — put a verdict on a diagram that 003 says must not drive anything. Asking the
declarations directly is a smaller question with the same answer.

**Where they will meet, and on whose terms.** When 003's records and 004's composed
candidates are ordinary result types, they render through the same door — a costed path is a
costed path. Nothing here waits on either, and nothing here should grow a special case for
either.

## D7 — A refusal renders as a typed refusal, never as an empty diagram

**Decision.** `render_path` returns `Diagram | NothingToDraw`, where `NothingToDraw` carries
the refusal's own reason verbatim.

**Rationale.** FR-011, SC-010, and predecessor defect B10. An empty diagram is
indistinguishable from a graph with nothing in it, and the input here is already a typed
refusal carrying a reason — discarding it at the render step would be losing the one piece
of information the caller needs. *Exit cost unknown* renders in the place the exit would
occupy, as itself.

## D8 — One regime per diagram, required by the signature

**Decision.** `render_graph` takes a `regime` parameter. There is no overload, default or
sentinel that renders every route at once.

**Rationale.** FR-019: a merged graph that exists under no regime must not be *producible*.
The strongest reading of "not producible" is that no argument list expresses it — a runtime
check can be bypassed by the next caller, a missing parameter cannot.

## D9 — Deterministic to the byte, which means every iteration is sorted

**Decision.** Venues sorted by id, routes by id, legs by index, edges emitted in that order.
No `set` is iterated, no `dict` is relied on for order.

**Rationale.** FR-016 and SC-003 require byte-identical output across separate runs and
processes. Golden files are one of the two delivery targets, so any nondeterminism shows up
as a spurious diff in the suite rather than as a subtle wrong answer — annoying rather than
dangerous, but it would train everyone to regenerate goldens without reading them, which is
how a real change slips through.

## D10 — Mermaid text is written by hand; no rendering dependency

**Decision.** String construction in this repo. No mermaid library, no templating engine.

**Rationale.** The output is a few kinds of line. A dependency here would put a third party
between a declaration and its picture, would need pinning and auditing under the
no-phone-home rule, and would make the escaping in D3 someone else's semantics.

## D11 — The script is a printer, not a program

**Decision.** `scripts/render_diagram.py`, beside `scripts/check_provenance.py`: parses a
minimal argument set, calls the `api` function, prints to stdout. No file writing, no
reports directory, no formatting logic of its own.

**Rationale.** FR-021 and owner decision D-B. The delivery surface is deliberately minimal
and recorded as such; keeping every decision in `api` means the script has nothing in it
worth testing, which is the point. `scripts/` rather than `terezy.cli` because this is a
developer and debugging tool, and the CLI is a delivery surface whose shape is still
deferred.
