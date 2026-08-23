"""**E10** by hand: a run whose events straddle an effective date charges both rates.

SC-003 and SC-004, with the arithmetic written out beside every assertion. One projection,
one instrument, one tax class -- and two rates, because the class's schedule steps in the
middle of the holding. The old rate applies before the step and the new one from it, in the
same run, with no branch in the engine and no source change when the next step is declared.

**The schedule here is a FIXTURE and its dates are invented.** It is shaped like the
Ukrainian military levy's 1.5% -> 5% step because that is the shape the domain has
(``SIMULATOR_SPEC.md`` §4.5.1), but the dates are chosen to fall inside this synthetic
bond's coupon schedule and they claim nothing about any legislation. The real classes in
``data/tax/ua.toml`` carry one entry each, dated by what their citation attests, and the
spec is explicit that the historic levy step is *not* entered until a citation supplies its
date.

---

**The bond** (``tests/synthetic.py``): 10 units x 1 000.00 face at 15.5%, semiannual,
``act/365``, issued 2026-01-15, maturing 2028-01-15 (paid 2028-01-17, the following
Monday). Annual interest on the holding is 10 x 1 000.00 x 0.155 = 1 550.00, and each
coupon is that scaled by the period's days over 365:

| # | Paid | Days accrued | Coupon |
|---|---|---|---|
| 1 | 2026-07-15 | 181 | 1 550.00 x 181/365 = **768.6301369863013** |
| 2 | 2027-01-15 | 184 | 1 550.00 x 184/365 = **781.3698630136986** |
| 3 | 2027-07-15 | 181 | 1 550.00 x 181/365 = **768.6301369863013** |
| 4 | 2028-01-17 | 184 | 1 550.00 x 184/365 = **781.3698630136986** |

The four sum to 1 550.00 x 730/365 = 3 100.00 exactly, which is the check that the table
is right before any tax is applied to it.

**The schedule**: 18% PIT throughout, and a levy that steps from 1.5% to 5% on 2027-01-01.
Coupon 1 falls before the step; coupons 2, 3 and 4 fall on or after it.

Each charge is the base times each rate, on two lines:

| # | Entry from | PIT line              | Levy line              | Charge              |
|---|------------|-----------------------|------------------------|---------------------|
| 1 | 2026-01-01 | 138.35342465753423    | 11.52945205479452      | 149.88287671232875  |
| 2 | 2027-01-01 | 140.64657534246576    | 39.06849315068493      | 179.7150684931507   |
| 3 | 2027-01-01 | 138.35342465753423    | 38.431506849315065     | 176.7849315068493   |
| 4 | 2027-01-01 | 140.64657534246576    | 39.06849315068493      | 179.7150684931507   |

    PIT  = coupon x 0.18                       for every one of the four
    levy = coupon x 0.015  (coupon 1)
         = coupon x 0.05   (coupons 2, 3, 4)

The redemption is at par -- 10 units bought for 10 000.00 and repaid 10 000.00 -- so the
realised gain is zero and the disposal charge is zero under either entry. That is stated
rather than left implicit: a zero charge here is the exemption-shaped case, and it is
recorded as a charge like any other.

**Coupons 1 and 3 pay exactly the same amount**, which is what makes the step measurable
rather than merely visible: the difference between their charges is the base times the
step in the levy and nothing else,

    176.7849315068493 - 149.88287671232875 = 26.902054794520546
    768.6301369863013 x (0.05 - 0.015)     = 26.902054794520546
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Final

import pytest

from terezy.core.ledger.events import EventKind
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import is_close
from terezy.core.results import project
from terezy.core.results.project import Projection
from terezy.core.tax.interface import TaxableEventKind, TaxCharge, TaxClass
from terezy.core.tax.schedule import RateEntry
from terezy.data.declarations import loader
from tests import synthetic

pytestmark = pytest.mark.worked_example

CLASS_ID: Final = "fixture_stepped_levy"
STEP_DATE: Final = date(2027, 1, 1)
FIRST_ENTRY_FROM: Final = date(2026, 1, 1)

PIT_RATE: Final = 0.18
LEVY_BEFORE: Final = 0.015
LEVY_AFTER: Final = 0.05

# The four coupons, from the table in the module docstring.
COUPON_181: Final = 1_550.00 * 181 / 365
COUPON_184: Final = 1_550.00 * 184 / 365

# The four charges, likewise. Written as the arithmetic rather than as literals, so a
# reader checks the *rule* -- base times rate, twice, on two lines -- and not a number
# somebody once pasted in.
CHARGE_1: Final = COUPON_181 * PIT_RATE + COUPON_181 * LEVY_BEFORE
CHARGE_2: Final = COUPON_184 * PIT_RATE + COUPON_184 * LEVY_AFTER
CHARGE_3: Final = COUPON_181 * PIT_RATE + COUPON_181 * LEVY_AFTER
CHARGE_4: Final = CHARGE_2


def _sources(name: str) -> Provenance:
    return prov.of(
        [
            SourceRef(
                id=f"fixture:{name}",
                citation=(
                    "FIXTURE — an invented dated rate entry. Not a claim about any "
                    "legislation, and not a date read off one."
                ),
                retrieved_on=date(2026, 8, 23),
                verified_on=None,
            )
        ]
    )


def _stepped_class() -> TaxClass:
    """18% PIT throughout, levy 1.5% then 5% from 2027-01-01. Both entries cited."""
    return TaxClass(
        id=CLASS_ID,
        applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
        rates=(
            RateEntry(
                effective_from=FIRST_ENTRY_FROM,
                pit_rate=PIT_RATE,
                levy_rate=LEVY_BEFORE,
                provenance=_sources("before_the_step"),
            ),
            RateEntry(
                effective_from=STEP_DATE,
                pit_rate=PIT_RATE,
                levy_rate=LEVY_AFTER,
                provenance=_sources("after_the_step"),
            ),
        ),
    )


def _projected(declared: TaxClass) -> Projection:
    outcome = project.project(
        synthetic.declaration(
            tax_classes={
                TaxableEventKind.COUPON: declared.id,
                TaxableEventKind.DISPOSAL_GAIN: declared.id,
            }
        ),
        synthetic.holding(),
        synthetic.horizon(),
        synthetic.assumptions(),
        tax_classes={declared.id: declared},
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _coupon_charges(projection: Projection) -> list[TaxCharge]:
    """The charges on coupon events, in date order, paired with what they were charged on."""
    coupons = {
        event.sequence for event in projection.ledger.applied if event.kind is EventKind.COUPON
    }
    return [charge for charge in projection.charges if charge.event_sequence in coupons]


class TestOneRunTwoRates:
    """SC-003: the old rate before the effective date, the new rate on and after it."""

    def test_the_four_coupons_are_the_hand_computed_amounts(self) -> None:
        # Checked before any tax is applied: a tax assertion against a wrong coupon would
        # be a passing test of a wrong number.
        amounts = [
            charge.taxable_base.amount for charge in _coupon_charges(_projected(_stepped_class()))
        ]
        assert len(amounts) == 4
        assert is_close(amounts[0], COUPON_181)
        assert is_close(amounts[1], COUPON_184)
        assert is_close(amounts[2], COUPON_181)
        assert is_close(amounts[3], COUPON_184)
        assert is_close(sum(amounts), 3_100.00), "1 550.00 x 730/365 over exactly two years"

    def test_each_coupon_is_charged_at_the_entry_in_force_on_its_own_date(self) -> None:
        charges = _coupon_charges(_projected(_stepped_class()))
        assert is_close(charges[0].total.amount, CHARGE_1)  # 149.88287671232875, levy 1.5%
        assert is_close(charges[1].total.amount, CHARGE_2)  # 179.7150684931507,  levy 5%
        assert is_close(charges[2].total.amount, CHARGE_3)  # 176.7849315068493,  levy 5%
        assert is_close(charges[3].total.amount, CHARGE_4)  # 179.7150684931507,  levy 5%

    def test_pit_is_unchanged_across_the_step_and_only_the_levy_moves(self) -> None:
        # The two lines exist so a change to one is visible without unpicking a blend.
        # Here the schedule steps the levy alone, and the PIT line proves it.
        charges = _coupon_charges(_projected(_stepped_class()))
        assert is_close(charges[0].pit.amount, COUPON_181 * PIT_RATE)
        assert is_close(charges[2].pit.amount, COUPON_181 * PIT_RATE)
        assert is_close(charges[0].levy.amount, COUPON_181 * LEVY_BEFORE)
        assert is_close(charges[2].levy.amount, COUPON_181 * LEVY_AFTER)

    def test_the_difference_between_two_equal_coupons_is_exactly_the_step(self) -> None:
        """Coupons 1 and 3 are the same amount, so their charges differ by the step alone.

        This is SC-003's measurable half. Two charges being "different" would be satisfied
        by any bug that varied a rate; a difference equal to base x (0.05 - 0.015) can only
        come from the schedule doing what it says.
        """
        charges = _coupon_charges(_projected(_stepped_class()))
        assert is_close(charges[0].taxable_base.amount, charges[2].taxable_base.amount)
        assert is_close(
            charges[2].total.amount - charges[0].total.amount,
            COUPON_181 * (LEVY_AFTER - LEVY_BEFORE),
        )

    def test_a_charge_carries_the_citation_of_the_entry_that_produced_it(self) -> None:
        """Per entry, not per class: the two entries are two observations (research.md D1)."""
        charges = _coupon_charges(_projected(_stepped_class()))
        before = {ref.id for ref in charges[0].provenance.sources}
        after = {ref.id for ref in charges[2].provenance.sources}
        assert "fixture:before_the_step" in before
        assert "fixture:after_the_step" not in before
        assert "fixture:after_the_step" in after
        assert "fixture:before_the_step" not in after

    def test_the_redemption_at_par_is_charged_zero_and_the_zero_is_recorded(self) -> None:
        # 10 units bought for 10 000.00 and repaid 10 000.00: the realised gain is zero, so
        # both rates give zero. Recorded as a charge, because a missing charge and an
        # exempt one are different claims.
        projection = _projected(_stepped_class())
        coupons = {charge.event_sequence for charge in _coupon_charges(projection)}
        (disposal,) = [
            charge for charge in projection.charges if charge.event_sequence not in coupons
        ]
        assert disposal.taxable_base.amount == 0.0
        assert disposal.total.amount == 0.0
        assert disposal.provenance.sources, "the zero cites the entry that produced it"


class TestALegislatedChangeIsOneEntryInAFile:
    """SC-004, FR-013: entered as data, taking effect in the next run, no source touched."""

    JURISDICTION: Final = """
[jurisdiction]
id            = "fixture"
name          = "FIXTURE jurisdiction — invented rates, not any real law"
base_currency = "UAH"

[[jurisdiction.tax_class]]
id         = "fixture_stepped_levy"
applies_to = ["coupon", "disposal_gain"]
note       = "FIXTURE — an invented class used by a worked example. Not a tax opinion."
"""

    def _entry(self, effective_from: str, levy_rate_pct: float) -> str:
        return f'''
  [[jurisdiction.tax_class.rate]]
  effective_from = "{effective_from}"
  pit_rate_pct   = 18.0
  levy_rate_pct  = {levy_rate_pct}
  note           = "FIXTURE — invented rates on an invented date. Not read off any statute."
  kind           = "tax_rule"
  source         = "FIXTURE — not an observation of anything."
  retrieved_on   = "2026-08-23"
  verified_on    = ""
'''

    def _charges_from(self, path: Path, text: str) -> list[TaxCharge]:
        path.write_text(text, encoding="utf-8")
        (declared,) = loader.tax_classes_from_file(path)
        return _coupon_charges(_projected(declared))

    def test_appending_one_dated_entry_changes_the_next_run_and_nothing_else(
        self, tmp_path: Path
    ) -> None:
        """The whole of FR-013, as a diff: one block of TOML, and the answer moves.

        The two runs go through the *same* loader, the same rule and the same projection
        function. Nothing is imported differently, no flag is set, and the only thing that
        changed between them is the text of a file.
        """
        path = tmp_path / "fixture.toml"
        one_entry = self.JURISDICTION + self._entry("2026-01-01", 1.5)
        before = self._charges_from(path, one_entry)

        two_entries = one_entry + self._entry("2027-01-01", 5.0)
        after = self._charges_from(path, two_entries)

        # Coupon 1 falls before the appended entry's date and is untouched, to the bit.
        assert before[0].total.amount == after[0].total.amount
        assert is_close(after[0].total.amount, CHARGE_1)
        # Coupons 2, 3 and 4 fall on or after it and move to the new levy.
        assert is_close(after[1].total.amount, CHARGE_2)
        assert is_close(after[2].total.amount, CHARGE_3)
        assert is_close(after[3].total.amount, CHARGE_4)
        for index in (1, 2, 3):
            assert before[index].total.amount != after[index].total.amount

    def test_the_change_is_one_block_of_toml_and_no_python_at_all(self, tmp_path: Path) -> None:
        """The claim SC-004 actually makes, asserted rather than assumed.

        The difference between the two files above is exactly one
        ``[[jurisdiction.tax_class.rate]]`` block. That is checked here on the text itself,
        because "no source lines changed" is otherwise a statement about a diff nobody in
        the test can see.
        """
        one_entry = self.JURISDICTION + self._entry("2026-01-01", 1.5)
        two_entries = one_entry + self._entry("2027-01-01", 5.0)
        appended = two_entries.removeprefix(one_entry)
        assert appended.count("[[jurisdiction.tax_class.rate]]") == 1
        assert one_entry in two_entries, "nothing already declared was edited"
        # And it loads, which is the other half: a change nobody can enter is not a change.
        path = tmp_path / "fixture.toml"
        path.write_text(two_entries, encoding="utf-8")
        (declared,) = loader.tax_classes_from_file(path)
        assert [entry.effective_from for entry in declared.rates] == [
            date(2026, 1, 1),
            STEP_DATE,
        ]
        assert [entry.levy_rate for entry in declared.rates] == [LEVY_BEFORE, LEVY_AFTER]


class TestTheBoundaryIsInclusive:
    """An event **on** the effective date is charged at the new entry, not the old one."""

    def test_a_coupon_dated_exactly_on_the_step_takes_the_new_rate(self) -> None:
        """2027-01-15 is after the step; the boundary itself is tested in the unit suite.

        Here the claim is narrower and worth making separately: the *projection* agrees
        with ``rate_on``. A boundary correct in the lookup and re-derived differently in
        the wiring would be a bug no unit test could see.
        """
        on_the_day = TaxClass(
            id=CLASS_ID,
            applies_to=frozenset({TaxableEventKind.COUPON, TaxableEventKind.DISPOSAL_GAIN}),
            rates=(
                RateEntry(
                    effective_from=FIRST_ENTRY_FROM,
                    pit_rate=PIT_RATE,
                    levy_rate=LEVY_BEFORE,
                    provenance=_sources("before_the_step"),
                ),
                RateEntry(
                    effective_from=date(2027, 1, 15),
                    pit_rate=PIT_RATE,
                    levy_rate=LEVY_AFTER,
                    provenance=_sources("on_the_coupon_date"),
                ),
            ),
        )
        charges = _coupon_charges(_projected(on_the_day))
        assert is_close(charges[0].levy.amount, COUPON_181 * LEVY_BEFORE)
        assert is_close(charges[1].levy.amount, COUPON_184 * LEVY_AFTER), (
            "the coupon paid on the effective date itself takes the new entry"
        )
