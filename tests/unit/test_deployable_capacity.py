"""FR-007: an undeclared income-tax rate is ``None``, and ``None`` is not zero.

*A stream MAY declare an income-tax rate, and deployable capacity MUST be reported net of
it, so the amount available to invest is never overstated.*

The word doing the work is **MAY**. A rate that was not declared is not a rate of zero: one
is *the owner has not said what is withheld*, the other is *the owner says nothing is*. They
are different claims about the same field, and the difference decides whether a figure may be
reported at all.

**Why this matters more than it looks.** Returning the gross when no rate was declared
produces a net figure that quietly equals the gross -- the single most plausible wrong number
in the whole module, because it is right whenever the rate happens to be zero and wrong by
the rate the rest of the time, with nothing in the output to say which case a reader is
looking at. That is the no-silent-default rule (Principle IV) applied to an optional field,
and this module is where it is asserted:

* a **declared** rate, including a declared zero, gives ``DeployableCapacity`` with every
  term of ``net = gross - withheld`` present;
* **no** declared rate gives ``IncomeTaxRateUndeclared``, which carries the gross, the reason,
  and **no net field at all** -- so there is nothing on it for a caller to read as an amount
  available to invest.

The two are unrelated types, on the ``RoundTripCost | ExitCostUnknown`` and ``RealRate |
RealTermsUnavailable`` precedent: a caller that forgot the second case is a mypy error rather
than a wrong figure in front of the owner.

## Every rate below is invented

The owner's own income-tax position has not been stated (``SIMULATOR_SPEC.md`` §11 item 3),
and this project may not put a real legal rate in as though it had been observed. The rates
here are round numbers chosen to make the arithmetic checkable by eye and chosen
*deliberately unlike* any real Ukrainian schedule, so nothing here can be mistaken for a
declaration of fact about tax.
"""

from __future__ import annotations

import dataclasses

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.tolerance import assert_money_close
from terezy.core.streams import streams
from terezy.core.streams.streams import DeployableCapacity, IncomeStream, IncomeTaxRateUndeclared
from tests.invariants import route_graphs

GROSS = 100_000.0
"""What arrives each month, gross. Invented, and round so that every product below is exact
in binary floating point -- the arithmetic under test is the module's, not the float's."""

RATE = 0.1
"""An invented withholding rate: ten percent. Not any real schedule; see the module
docstring. Ten percent of a hundred thousand is ten thousand, which is checkable by eye."""

STREAM_SOURCE = SourceRef(
    id="synthetic:stream-declaration",
    citation="SYNTHETIC FIXTURE -- a stream declaration that did carry a source.",
    retrieved_on=route_graphs.RETRIEVED_ON,
    verified_on=None,
)
STREAM_SOURCES: Provenance = prov.of([STREAM_SOURCE])
"""A mark on the gross amount, so propagation through the withholding can be asserted.

Real stream declarations carry **no** source -- an owner's own salary is a statement of fact
by the only person who can make it, and the exemption is argued in
``contracts/declaration-schema.md``. So this fixture asserts the *mechanism* rather than the
current data: if a gross amount ever does rest on a source, every figure derived from it must
still admit as much (FR-022).
"""


def _stream(*, rate: float | None, gross: float = GROSS) -> IncomeStream:
    """The hryvnia salary with a stated gross and a stated -- or unstated -- rate."""
    return dataclasses.replace(
        route_graphs.SALARY_UAH,
        amount=Money(gross, Currency.UAH, STREAM_SOURCES),
        income_tax_rate=rate,
    )


def _capacity(*, rate: float, gross: float = GROSS) -> DeployableCapacity:
    """Deployable capacity for a stream that declares a rate, narrowed to the figure."""
    outcome = streams.deployable(_stream(rate=rate, gross=gross))
    assert isinstance(outcome, DeployableCapacity), outcome
    return outcome


class TestAnUndeclaredRateProducesNoNetFigureAtAll:
    """The heart of FR-007. ``None`` means nobody said, and nobody said is not zero."""

    def test_a_stream_with_no_declared_rate_reports_that_rather_than_a_figure(self) -> None:
        outcome = streams.deployable(_stream(rate=None))
        assert isinstance(outcome, IncomeTaxRateUndeclared)
        assert outcome.stream_id == route_graphs.SALARY_UAH.id

    def test_the_reason_says_no_income_tax_rate_is_declared(self) -> None:
        # The output has to say it in words, not merely in a type: FR-017 wants every
        # degraded outcome to carry its reason, and the reason is what reaches the reader.
        outcome = streams.deployable(_stream(rate=None))
        assert isinstance(outcome, IncomeTaxRateUndeclared)
        assert "no income-tax rate declared" in outcome.reason
        assert "not a rate of zero" in outcome.reason

    def test_the_record_has_nowhere_for_a_net_figure_to_hide(self) -> None:
        # The structural half, and the one that actually holds the line: no field named for
        # an amount available to invest exists on this record, so no caller can read one off
        # it and no future edit can quietly start filling one in. Same guarantee as
        # ``ExitCostUnknown`` carrying no ``fraction``.
        fields = {field.name for field in dataclasses.fields(IncomeTaxRateUndeclared)}
        assert fields == {"reason", "stream_id", "gross"}
        assert not fields & {"net", "withheld", "income_tax_rate", "deployable", "amount"}

    def test_the_gross_is_still_reported_because_it_is_still_known(self) -> None:
        # An upper bound is worth more than nothing, and refusing to report the arrival at
        # all would be its own kind of dishonesty. What the record does not do is call it
        # ``net`` or claim the two are equal.
        outcome = streams.deployable(_stream(rate=None))
        assert isinstance(outcome, IncomeTaxRateUndeclared)
        assert_money_close(outcome.gross, Money(GROSS, Currency.UAH, prov.EMPTY))

    def test_it_is_not_a_deployable_capacity_and_cannot_be_used_as_one(self) -> None:
        # Unrelated types, so the mistake is a mypy error rather than a wrong number. The
        # runtime half of that claim: neither is an instance of the other, and they share no
        # base beyond ``object``.
        undeclared = streams.deployable(_stream(rate=None))
        assert not isinstance(undeclared, DeployableCapacity)
        assert DeployableCapacity.__bases__ == (object,)
        assert IncomeTaxRateUndeclared.__bases__ == (object,)


class TestADeclaredZeroIsADifferentClaimFromNoRateAtAll:
    """The distinction that makes the whole thing worth having.

    Both cases produce a net figure equal to the gross. Only one of them is *reported* as a
    net figure, and it is the one where the owner said so.
    """

    def test_a_declared_zero_gives_a_net_figure_equal_to_the_gross(self) -> None:
        # Bit-identical, not merely close: multiplying by zero and subtracting the result is
        # exact, and a gross that came back changed in the last bits would mean an
        # arithmetic path nobody asked for.
        capacity = _capacity(rate=0.0)
        assert capacity.income_tax_rate == 0.0
        assert capacity.withheld.amount == 0.0
        assert capacity.net.amount.hex() == capacity.gross.amount.hex()

    def test_the_two_cases_are_told_apart_by_type_and_not_by_reading_a_number(self) -> None:
        # The two figures are equal; the two answers are not. This is the assertion that
        # would fail if ``deployable`` ever returned the gross for an undeclared rate.
        declared_zero = streams.deployable(_stream(rate=0.0))
        undeclared = streams.deployable(_stream(rate=None))
        assert isinstance(declared_zero, DeployableCapacity)
        assert isinstance(undeclared, IncomeTaxRateUndeclared)
        assert declared_zero.net.amount == undeclared.gross.amount
        # That the two types are *not* interchangeable is proved statically and cannot be
        # written here: mypy rejects ``type(a) is not type(b)`` on these two as a
        # non-overlapping identity check, because their bases are disjoint. The type checker
        # refusing to compare them **is** the guarantee, and asserting it at runtime would
        # only be asserting that mypy ran (the same note as in ``test_cost_labels``).


class TestADeclaredRateIsAppliedAndShown:
    """FR-007's arithmetic, hand-computed, with every term of it reported."""

    def test_ten_percent_of_a_hundred_thousand_leaves_ninety_thousand(self) -> None:
        #   gross    = 100 000.00 UAH
        #   withheld = 100 000 x 0.1 =  10 000.00 UAH
        #   net      = 100 000 - 10 000 = 90 000.00 UAH
        capacity = _capacity(rate=RATE)
        assert_money_close(capacity.withheld, Money(10_000.0, Currency.UAH, prov.EMPTY))
        assert_money_close(capacity.net, Money(90_000.0, Currency.UAH, prov.EMPTY))
        assert capacity.income_tax_rate == RATE

    def test_the_withheld_amount_is_reported_and_not_merely_implied(self) -> None:
        # ``net = gross - withheld`` with all three present, so the figure can be checked by
        # reading it. A net amount that did not show what it was net *of* would be exactly
        # as opaque as the gross it replaced.
        capacity = _capacity(rate=RATE)
        assert_money_close(
            capacity.net,
            Money(capacity.gross.amount - capacity.withheld.amount, Currency.UAH, prov.EMPTY),
        )

    def test_the_figure_says_which_stream_and_which_period_it_is_for(self) -> None:
        # A monthly figure read as an annual one is wrong by a factor of twelve, and two
        # streams' capacities must not be addable by accident, so the record names both.
        capacity = _capacity(rate=RATE)
        assert capacity.stream_id == route_graphs.SALARY_UAH.id
        assert capacity.cadence == "monthly"

    def test_the_currency_survives_the_withholding(self) -> None:
        capacity = _capacity(rate=RATE)
        assert capacity.gross.currency is Currency.UAH
        assert capacity.withheld.currency is Currency.UAH
        assert capacity.net.currency is Currency.UAH

    def test_the_mark_on_the_gross_reaches_the_net(self) -> None:
        # FR-022: a figure derived from an unverified value inherits the mark. Nothing in
        # this arithmetic may launder it out -- and nothing can, because ``money``'s
        # functions only ever union provenance.
        capacity = _capacity(rate=RATE)
        assert STREAM_SOURCE in capacity.net.provenance.sources
        assert STREAM_SOURCE in capacity.withheld.provenance.sources
        assert prov.is_unverified(capacity.net.provenance)


class TestNothingIsClamped:
    """B13's rule reaching a new place: a mis-entered rate is reported, not softened."""

    def test_a_rate_above_one_produces_a_negative_net_figure_and_says_so(self) -> None:
        #   withheld = 100 000 x 1.5 = 150 000
        #   net      = 100 000 - 150 000 = -50 000
        # Absurd, and reported as absurd. A ``max(net, 0)`` here would turn a declaration
        # nobody could have meant into a plausible-looking zero -- predecessor defect B13 in
        # a new place, and a defect that hides its own cause.
        capacity = _capacity(rate=1.5)
        assert_money_close(capacity.net, Money(-50_000.0, Currency.UAH, prov.EMPTY))
        assert capacity.net.amount < 0.0

    def test_a_negative_rate_leaves_more_than_arrived_rather_than_being_swallowed(self) -> None:
        # The other direction, equally absurd and equally reported. The range check belongs
        # to the loader, where the error can name the file and the field; what this module
        # must not do is quietly make the figure look reasonable.
        capacity = _capacity(rate=-0.2)
        assert_money_close(capacity.net, Money(120_000.0, Currency.UAH, prov.EMPTY))

    def test_a_zero_gross_stays_zero_in_every_term(self) -> None:
        # The degenerate case, which is the honest state of the declaration files today:
        # ``amount = 0.0`` because the owner's real figures have not been stated. A zero
        # produces a zero result rather than a made-up one.
        capacity = _capacity(rate=RATE, gross=0.0)
        assert capacity.gross.amount == 0.0
        assert capacity.withheld.amount == 0.0
        assert capacity.net.amount == 0.0


class TestTheRecordsCarryDataAndNothingElse:
    """Owner decision D-E, asserted rather than trusted."""

    @pytest.mark.parametrize(
        "record", [IncomeStream, DeployableCapacity, IncomeTaxRateUndeclared, streams.Indexation]
    )
    def test_no_record_in_the_module_carries_behaviour(self, record: type) -> None:
        assert [
            name for name, value in vars(record).items() if callable(value) and "__" not in name
        ] == []

    def test_the_records_are_frozen(self) -> None:
        stream = _stream(rate=RATE)
        with pytest.raises(dataclasses.FrozenInstanceError):
            stream.income_tax_rate = 0.0  # type: ignore[misc]
