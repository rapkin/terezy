"""``flat_rate``: apply whatever rates the declared class carries **on the event's date**.

No rates live here, and no dates either. The whole rule is "find the entry in force on the
event's date, then multiply the base by its two rates, on two lines". That is not a
placeholder for something richer: a flat rate on a stated base is genuinely what Ukrainian
PIT and the military levy do to investment income, and every case that is more complicated
than this (foreign withholding credits, loss offset, annualisation) is a *different rule*,
which arrives as another entry in the registry rather than as a branch here.

⚙ **Feature 006 made the rates a dated schedule** (research.md D1, required test E10). The
selection is one call to :func:`terezy.core.tax.schedule.rate_on`, and the date it selects
on is the date the ledger event occurred -- so a run whose events straddle a legislated
change charges the old rate before it and the new rate from it, with no branch here and no
source change when the next change is declared.

**There is no exempt rule, and there is no exempt branch.** The exemption is this
function applied to a class declaring zeroes -- data, not code. If the exempt case needed
its own function the abstraction would be wrong, and it would be wrong in the most
expensive possible place: the moment a second exempt instrument appeared, the branch would
have to learn about it, and Principle II would be violated for the sake of an ``if``.

Read that together with what this module refuses to do. A class that does not cover the
income kind it is asked about gets a typed refusal, not a zero. "The rule does not apply
here" and "the rule applied and charged nothing" are opposite claims about the money, and
only one of them has a citation behind it. Silently turning the first into the second is
the dangerous default the whole tax interface is shaped to prevent, because the
comfortable answer -- untaxed -- is also the wrong one.
"""

from __future__ import annotations

from terezy.core.errors import TaxFailure, UnresolvedTaxClass
from terezy.core.ledger.events import Event
from terezy.core.primitives import money
from terezy.core.primitives import provenance as prov
from terezy.core.tax.interface import TaxCharge, TaxClass, TaxContext, TaxRuleOps
from terezy.core.tax.schedule import RateUndeclaredBefore, rate_on


def charge(event: Event, tax_class: TaxClass, context: TaxContext) -> TaxCharge | TaxFailure:
    """Charge ``pit_rate`` and ``levy_rate`` against the context's base, as two lines.

    **Both lines are computed from the base independently**, rather than from a single
    combined rate. In this rule the two bases are the same amount, and adding the rates
    would give the same total today -- and would make the two lines unrecoverable
    tomorrow. A foreign withholding credit applies against PIT and not against the levy;
    a blended figure cannot express that at all, and unpicking it later means guessing
    which part of a total was which. The structure is built now for exactly the reason
    currency tagging is.

    **The rates come from the entry in force on the event's date.** An event dated before
    the schedule's earliest entry returns ``RateUndeclaredBefore`` rather than a charge:
    no rate is defaulted and no zero is silently charged (FR-012). That refusal is what
    makes an honest schedule safe to declare -- a class may start at the date its citation
    attests, and everything earlier stops the run instead of being quietly covered.

    **Provenance is unioned, not chosen.** Each line goes through
    ``money.scale_sourced``, which merges the *entry's* sources into the base's, so the
    resulting zero *cites the exemption that produced it*. That citation is the evidence
    the exemption was applied. The entry's rather than the class's: two rates cited by two
    sources are two observations, and one of them may be verified while the other is not.

    **A negative base yields a negative charge**, and is deliberately not clamped. A
    realised loss times a declared rate is what this rule computes; whether that loss is
    actually creditable against other income is a loss-offset rule this feature does not
    model, and the honest way to say so is a visible line computed as declared rather
    than a zero that quietly asserts the answer. Clamping would be the silent clamp the
    constitution puts in its top severity class. The feature that introduces loss offset
    must revisit this, and the note is here so it is found.
    """
    if context.taxable_event not in tax_class.applies_to:
        return UnresolvedTaxClass(
            tax_class_id=tax_class.id,
            instrument_id=context.instrument_id,
            reason=(
                f"tax class {tax_class.id!r} does not cover "
                f"{context.taxable_event.value!r} income, so it cannot say what is owed "
                f"on event {event.sequence}. Refused rather than charged at zero: "
                "'this rule does not apply' and 'this rule charged nothing' are "
                "opposite claims, and only the second one is cited. Declare a class for "
                f"{context.taxable_event.value!r} on this instrument."
            ),
        )

    in_force = rate_on(tax_class, event.occurred_on)
    if isinstance(in_force, RateUndeclaredBefore):
        return in_force

    base = context.taxable_base
    pit = money.scale_sourced(base, in_force.pit_rate, in_force.provenance)
    levy = money.scale_sourced(base, in_force.levy_rate, in_force.provenance)
    return TaxCharge(
        event_sequence=event.sequence,
        pit=pit,
        levy=levy,
        total=money.add(pit, levy),
        taxable_base=base,
        tax_class_id=tax_class.id,
        charged_for_year=context.charged_for_year,
        provenance=prov.merge(base.provenance, in_force.provenance),
    )


OPS = TaxRuleOps(charge=charge)
"""This module's implementation of the ``TaxRule`` interface, as one record of functions."""
