"""SC-009: no statistical metric for an assumption-driven instrument, and no field for one.

Constitution Principle I in its most literal form: *for an assumption-driven instrument the
engine must refuse to emit [volatility, Sharpe, Sortino], not compute them from invented
data.* Both Inzhur funds are assumption-driven — their numbers come from what the fund says
about itself, and there is no price history behind any of them.

**The refusal is asserted twice, from opposite directions, and the second is the one that
lasts.** A function that refuses can be worked around by whoever wants a number; a *record
with nowhere to put one* cannot. So this module both calls the refusal and walks every
field of every fund result record looking for somewhere a statistic could be written.

**It also walks the shipped declarations**, because the label has to be true of the data
and not only of the types: a fund file that ever declared itself observed rather than
assumption-driven would make every prohibition here vacuous for that fund.
"""

from __future__ import annotations

import dataclasses
import inspect
from pathlib import Path
from typing import Any, Final

import pytest

import terezy.core.results.fund as fund_results
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.results.fund import (
    BesideTheHurdle,
    ClassSubtotal,
    DistributionLine,
    ExitLine,
    FundProjection,
    MetricRefused,
    RangeProjection,
    statistical_metric,
)
from terezy.data.declarations import resolver

pytestmark = pytest.mark.contract

DATA_ROOT: Final = Path(__file__).resolve().parents[2] / "data"

FORBIDDEN: Final[tuple[str, ...]] = (
    "volatility",
    "sharpe",
    "sortino",
    "beta",
    "stdev",
    "std_dev",
    "standard_deviation",
    "variance",
    "drawdown",
    "var_95",
    "value_at_risk",
    "correlation",
    "tracking_error",
    "information_ratio",
)
"""Every name a statistic could plausibly arrive under.

Wider than :data:`terezy.core.results.fund.STATISTICAL_METRICS`, deliberately: that list is
what a caller might *ask* for, and this one is what a field might be *called* by somebody
adding it in good faith. A narrow list would pass the day the field was named
``annualised_stdev``.
"""

RESULT_RECORDS: Final = (
    FundProjection,
    RangeProjection,
    ClassSubtotal,
    DistributionLine,
    ExitLine,
    BesideTheHurdle,
)
"""Every record a fund run hands out. Listed *and* cross-checked against the module below,
so a new record cannot be added without either appearing here or failing the totality
test."""


def _funds() -> dict[str, FundDeclaration]:
    return dict(resolver.from_data_root(DATA_ROOT).funds)


class TestTheMetricIsRefused:
    """FR-005: a typed refusal carrying its reason, never a number."""

    @pytest.mark.parametrize("metric", fund_results.STATISTICAL_METRICS)
    def test_every_named_metric_is_refused_for_every_shipped_fund(self, metric: str) -> None:
        for identifier, declared in _funds().items():
            refused = statistical_metric(declared, metric)
            assert isinstance(refused, MetricRefused)
            assert refused.instrument_id == identifier
            assert refused.metric == metric
            assert refused.reason

    def test_the_reason_says_why_rather_than_merely_that(self) -> None:
        """A refusal a reader cannot act on is a refusal they will route around."""
        (declared,) = [item for item in _funds().values() if item.id == "inzhur_reit"]
        refused = statistical_metric(declared, "sharpe")
        assert "assumption-driven" in refused.reason
        assert "no price history" in refused.reason

    def test_the_signature_cannot_return_a_number_at_all(self) -> None:
        """The strongest form of the prohibition available in a type annotation.

        A ``float | MetricRefused`` would be a signature somebody eventually makes return
        the float. There is no input to this function that produces one.
        """
        signature = inspect.signature(statistical_metric)
        assert signature.return_annotation == "MetricRefused"


class TestThereIsNowhereToPutOne:
    """The structural half, and the half that survives a contributor in a hurry."""

    @pytest.mark.parametrize("record", RESULT_RECORDS)
    def test_no_fund_result_record_has_a_field_a_statistic_could_live_in(
        self, record: type[Any]
    ) -> None:
        offenders = [
            field.name
            for field in dataclasses.fields(record)
            if any(forbidden in field.name.casefold() for forbidden in FORBIDDEN)
        ]
        assert not offenders, (
            f"{record.__name__} has field(s) a statistic could be written into: "
            f"{offenders}. An assumption-driven instrument has no history to compute one "
            "from, and a caveated number gets copied without its caveat (Principle I)."
        )

    def test_no_fund_result_record_has_a_field_a_computed_fee_could_live_in(self) -> None:
        """research.md D9's structural absence, checked the same way.

        Owner decision B: the fee clauses are provenance context for the declared net
        yield and nothing accrues from them. A ``management_fee`` field on a result would
        be an invitation to start.
        """
        offenders = [
            f"{record.__name__}.{field.name}"
            for record in RESULT_RECORDS
            for field in dataclasses.fields(record)
            if "fee" in field.name.casefold()
        ]
        assert not offenders, offenders

    def test_the_listed_records_are_every_record_the_module_hands_out(self) -> None:
        """Otherwise the scan above covers whatever somebody remembered to list.

        Walked from the module rather than trusted, so a seventh result record either
        joins the list or fails here.
        """
        declared = {
            value
            for name, value in vars(fund_results).items()
            if not name.startswith("_")
            and inspect.isclass(value)
            and dataclasses.is_dataclass(value)
            and value.__module__ == fund_results.__name__
        }
        refusals = {
            fund_results.PurchaseAfterCutoff,
            fund_results.RedemptionRefused,
            fund_results.MetricRefused,
            fund_results.PegUnsizable,
            fund_results.AwaitingVerification,
            fund_results.FundAssumptions,
        }
        assert declared - refusals == set(RESULT_RECORDS)


class TestTheLabelIsTrueOfTheData:
    """FR-004: both shipped funds declare it, and the type has no other case."""

    def test_every_shipped_fund_is_assumption_driven(self) -> None:
        for declared in _funds().values():
            assert declared.is_assumption_driven is True

    def test_the_field_is_a_literal_with_no_false_case(self) -> None:
        """A bool would be a field a file could set the other way; a ``Literal[True]`` is not."""
        annotation = FundDeclaration.__annotations__["is_assumption_driven"]
        assert "Literal[True]" in str(annotation)


class TestEveryProjectionSaysWhatItRestsOn:
    """FR-004's positive half: labelled as declared terms and stated assumptions.

    The prohibition alone would leave a reader with a clean-looking number and no idea what
    kind of number it is. ``rests_on`` is what says so in words, and it is asserted here
    rather than only in the worked examples because it is a property of *every* fund
    result, not of one scenario.
    """

    def test_rests_on_is_a_required_field_and_not_an_optional_note(self) -> None:
        field = {item.name: item for item in dataclasses.fields(FundProjection)}["rests_on"]
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING

    def test_the_excludes_statement_is_required_too(self) -> None:
        field = {item.name: item for item in dataclasses.fields(FundProjection)}["excludes"]
        assert field.default is dataclasses.MISSING
        assert field.default_factory is dataclasses.MISSING
