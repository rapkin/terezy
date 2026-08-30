# Quickstart: the ФОП group 3 regime

The file-level rules are [contracts/taxation-scheme-declaration.md](./contracts/taxation-scheme-declaration.md);
the records are [data-model.md](./data-model.md). This page is what to run and what to expect.

## Declare a scheme

`data/tax/schemes/<id>.toml`. Two components on a base, one charged per elapsed month:

```toml
[scheme]
id = "xx_scheme"; name = "…"; jurisdiction = "xx"; tax_currency = "UAH"
variant = "non_vat_payer"; reporting_cadence = "quarterly"; declared_for = "stream"

  [[scheme.rate_component]]
  id = "component_a"; name = "the name the law uses"
    [[scheme.rate_component.rate]]
    effective_from = "2025-01-01"; rate_pct = 1.0; note = "…"
    kind = "tax_rule"; source = "…"; retrieved_on = "2026-08-25"; verified_on = ""

  [[scheme.periodic_component]]
  id = "component_b"; name = "…"; period = "month"
    [[scheme.periodic_component.amount]]
    effective_from = "2026-01-01"; amount = 0.0; currency = "UAH"; note = "…"
    kind = "tax_rule"; source = "…"; retrieved_on = "2026-08-23"; verified_on = ""
```

A cited fact that must be recorded and **not applied** — a termination conditioned on an
event, say — is a `[[scheme.rate_component.context]]` block. It carries `not_applied_because`
so nobody reads the omission as an oversight.

## Point a stream at it

```toml
[[stream]]
id = "contract_usd"; owner_id = "owner-001"; currency = "USD"; amount = 0.0
cadence = "monthly"
arrives_at  = "deel"                  # the routing origin
credited_to = "fop"                   # the tax event's location — a different fact
tax_scheme  = "ua_fop_group_3_non_vat"
```

Omit `tax_scheme` and the deployable figure is `TaxTreatmentUndeclared`: no net field at all,
the gross reported as a known upper bound, and a stated reason. Omit `credited_to` and the
file does not load.

## Run it

```bash
uv run pytest tests/worked_examples/test_fop_scheme_charge.py -q   # the hand arithmetic
uv run pytest -m "contract or invariant" -q                        # the compliance suites
uv run pytest -q && uv run mypy && uv run lint-imports
uv run python scripts/check_provenance.py
uv run python scripts/check_methodology_refs.py                    # read the exit code
```

## What you should see

**A charge.** Two separately named lines on one hryvnia base, each naming its own rate, its
own cited source and its own verification date. No blended percentage anywhere — there is no
field for one.

**A base from the credit date.** `charge.conversion` carries the dollars, the credit date, the
observation's date, the rate and the quotation unit. Change the sale's market rate and the
base is bit-identical.

**A refusal with a name on it.** Income dated before a component's earliest entry names the
component and the date. A credit date the official-rate series does not cover names the
series, the pair, the date and the window it does cover — 011's own refusal, carried whole.
Neither is a zero and neither is a charge with a line missing.

**Three different nils.** *This scheme charges no such component*, *it was charged and came to
nothing*, and *it is declared and nothing is in force* are three types. The ЄСВ nil is the
second, and its source is the owner's own statement, so every figure resting on it renders
marked.

**A switch, where the destination is unsettled.** One labelled figure per computable reading —
three for a payment system, two for a bank account outside Ukraine, one each for a personal
card and a crypto exchange. Each says which reading produced it and carries that reading's
citations; none is the tax owed; and there is nowhere to put a number that combines two.

**A refusal, where nothing declared reaches the destination.** Naming the destination, the
scheme, and both of the things that would close it.

## Move a verdict

A verdict is expected to move, and moving one is meant to be cheap: change `verdict` and the
readings in `data/tax/destinations/ua.toml`, add the row to the register in `spec.md`, and add
the line to owner verification task 6. No source file changes. What closes an UNSETTLED
destination is an індивідуальна податкова консультація of the owner's own — his action, not a
research task.
