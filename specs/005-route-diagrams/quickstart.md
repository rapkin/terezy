# Quickstart: verifying 005-route-diagrams

**Date**: 2026-08-23

## Prerequisites

```bash
uv sync --all-extras --dev
```

Python 3.13. No network; `tests/conftest.py` blocks sockets. No new dependency — the Mermaid
text is written by hand (research.md D10).

## The one-command check

```bash
uv run pytest -q
```

## 1. Look at the output

```bash
uv run python scripts/render_diagram.py graph --regime wartime --mode topology
uv run python scripts/render_diagram.py graph --regime wartime --mode declared-figures
```

Paste either into any Mermaid renderer. This is a feature whose defects are visible, and the
fastest review is your own eyes on the picture before any assertion runs.

What to look for: every declared venue present; two routes between the same pair drawn as
two edges; a closed route marked and still there; a destination with no exit carrying its
*no exit declared* mark; and the mode named on the diagram itself.

## 2. The honesty of the picture

```bash
uv run pytest -m contract -k diagram -v
```

| Covers | Asserts |
|---|---|
| SC-004 | All six mark states render distinguishably — **with every style declaration stripped first**, so a mark carried only by a colour fails |
| SC-005 | One unverified route input marks 100% of the elements depicting figures derived from it |
| SC-006 | Every figure equals the input's figure through the one rule of FR-022 — and the grep that no second formatting exists anywhere in the package |
| SC-007 | A destination with no declared exit renders the explicit mark, not an omission |
| SC-012 | Topology-only and with-figures differ only by figures, and **neither** carries a computed ramp cost |
| SC-010 | A refusal yields `NothingToDraw` with the reason, never an empty diagram and never a drawn path |

SC-006 is the one to read if something drifts. The failure mode is not a wrong number, it is
a *second* rounding: one call site formatting to three decimals because two looked coarse.
The grep is what catches it, and it is the point of FR-022.

## 3. Determinism and hostile input

```bash
uv run pytest -m golden -k diagram -v
uv run pytest -k hostile -v
```

- **SC-003** — the same declarations render byte-identically across separate processes. If
  this flakes, something iterates a `set` or trusts a `dict` for order (research.md D9).
- **SC-008** — quotes, brackets, pipes, arrows and Cyrillic in declared names give valid
  Mermaid, and two venues whose ids differ only by a character that sanitising would
  flatten stay two nodes. That is the whole reason node ids are positional (research.md D3).
- **SC-011** — at least one route graph and one costed path are checked in as goldens.

A golden diff here is a real diff. Read it before regenerating it.

## 4. The gates

```bash
uv run ruff check . && uv run ruff format --check .
uv run mypy
uv run lint-imports
uv run python scripts/check_provenance.py
uv run pytest --cov
```

`lint-imports` is the one that matters most for this feature: the renderer is in `api`
precisely because `core` may not format, and the first instinct when a figure is awkward to
render will be to add a helper in `core`. The contract will refuse it.

## What "done" looks like

- All twelve success criteria have a named test.
- `docs/METHODOLOGY.md` gains the number-rendering rule — stated as *the* rule, with its
  decimal places and the fact that it rounds — and the mark vocabulary a diagram uses.
- `docs/REQUIRED_TESTS.md` flips no row; this feature closes none.
- No new dependency, and `core` is untouched.
