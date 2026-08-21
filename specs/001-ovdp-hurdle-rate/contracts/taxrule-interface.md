# Contract: the `TaxRule` plugin interface

**Date**: 2026-08-21

The second of the four plugin interfaces this feature implements. Its governing
constraint is the strictest in the project: **no tax value may originate from an
implementer's or an agent's memory** (constitution Principle I). Every rate comes from a
cited source entered as data, or it does not exist.

---

## The signatures

Per owner decision D-E this is a function signature plus a record of data, not a class.

```python
ChargeFn = Callable[[Event, TaxClass, TaxContext], TaxCharge | TaxFailure]


@dataclass(frozen=True)
class TaxRuleOps:
    """How a kind of tax rule behaves. Data, not an object."""

    charge: ChargeFn


REGISTRY: Final[Mapping[str, TaxRuleOps]] = {
    "flat_rate": flat_rate.OPS,  # covers the exempt case: a flat rate of zero
}
```

Note what the signature does **not** do: it takes the `TaxClass` as an argument rather
than closing over it. A rule is a stateless function; the rates live in the declared
class, which is data loaded from `data/tax/`. There is nothing to construct and nothing to
configure.

## Obligations on every implementation

**No rates in code.** The function reads its rates from the `TaxClass` passed in. A
literal rate in a Python file is a defect regardless of whether it happens to be correct
— including `0.0`.

**Provenance is mandatory and propagates.** `charge` returns amounts whose provenance
unions the event's provenance with the tax class's own, via the `money.*` combining
functions. E5 requires that a tax figure
render with its source and verification date, and that the mark reach everything
downstream.

**Zero is a charge, not an absence.** For the exempt class, `charge` returns a
`TaxCharge` of zero **carrying the exempt class's provenance** — not `None`, and not a
skipped event. This matters: a zero charge that cites the exemption is the evidence that
the exemption was applied; a missing charge is indistinguishable from a rule that never
ran. SC-002 requires the total be exactly zero, which is only checkable if the zeroes are
recorded.

**PIT and levy are separate bases.** The military levy is not a surcharge folded into the
rate. It is computed on its own base and reported as its own line, because the cases that
matter later — foreign withholding creditable against PIT but **not** against the levy —
are unrepresentable if the two are added together at source. Not exercised in this
feature, where both are zero, but the structure is built now for the same reason
currency tagging is.

**Explicit failure.** An unresolvable situation returns `TaxFailure` — a tagged union
member, not an exception (D-E) — carrying its reason. It does not raise, and it does not
silently charge zero — a zero charge means "the rule
applied and the result was zero", which is a completely different fact from "the rule
could not be applied".

## `TaxCharge`

| Field | Rule |
|---|---|
| `pit` | `Money`. Zero for the exempt class. |
| `levy` | `Money`. Computed on its own base, reported separately. |
| `total` | `money.add(pit, levy)`, same currency enforced. |
| `taxable_base` | `Money`. The amount the rates were applied to — recorded so a figure can be checked without re-deriving it. |
| `tax_class_id` | Which declared class produced this. |
| `provenance` | Union of the event's and the class's. |
| `charged_for_year` | Tax year the liability accrues to. Recorded now; payment timing arrives with a later feature. |

## Tax currency is not display currency

The constitution names three currency roles — base, tax, display — and says conflating any
two is a bug. In this feature all three are UAH, so nothing is exercised. The relevant
obligation is therefore negative: **do not collapse them**. `TaxCharge` amounts are in the
tax currency by definition, and no code in this feature may assume that equals the
display currency, because for foreign securities it will not.

## What implementations must NOT do

- **Net tax into the instrument's amounts.** Gross in, charge out, both recorded. The
  waterfall in spec §5.3 needs the gross figure and the charge as separate lines.
- **Assume a single class per instrument.** The instrument supplies a mapping from event
  kind to class id; a rule that ignores the event kind will apply the wrong treatment the
  moment an instrument has two.
- **Hold state.** There is no instance. Rates arrive as an argument on every call.
- **Carry timing logic.** Payment date, cash sourcing for the payment, and forced sales on
  insufficient cash are later features. This interface records what is owed and for which
  year.

## `flat_rate` — this feature's implementation

A module of free functions exporting `OPS: TaxRuleOps`. Applies whatever `pit_rate` and
`levy_rate` the declared class carries.

**There is no exempt rule.** The exemption is `flat_rate` applied to a class declaring
zeroes — data, not code. If the exempt case needed its own function or its own branch,
the abstraction would be wrong, and Principle II would be violated the moment a second
exempt instrument appeared.

Applied to `coupon` and `disposal_gain` per `ua_government_bond` in `data/tax/ua.toml`.

## Verified by

| Test | Asserts |
|---|---|
| `tests/worked_examples/test_ovdp_schedule.py` | D1 — total tax over the holding's life is exactly zero, and every zero charge cites the exemption |
| `tests/contract/test_provenance_propagation.py` | E5 — tax figures carry source and verification date; the mark reaches derived figures |
| `tests/contract/test_declaration_loading.py` | An instrument referencing an undeclared class fails at load, rather than being treated as untaxed |
| `tests/invariants/test_traceability.py` | C6 — every tax figure resolves to its event and its rule |

**The dangerous default this guards against**: an unresolved tax class silently becoming
"no tax". Nothing in this feature may treat a missing rule as an exemption — the two are
opposite claims, and only one of them is cited.
