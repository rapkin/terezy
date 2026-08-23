"""FR-004: both seams are anchored, and a mismatch names both sides.

**This is the part of the join that can be silently wrong**, which is why it is the first
thing built and the first thing tested (plan.md, Phase 2 note). Everything else in the feature
is a sum of calls that already work; the chaining rule is the join's own content.

Feature 004 shipped an exit chain anchored at **neither** end. Money moved between venues for
free, and the record still read as a coherent three-hop journey -- an arriving amount in one
currency beside a cost fraction computed in another. The same failure is available here at two
more seams::

    stream --[ way in ]--> (venue, currency) == where the purchase happens
    where the proceeds land == (venue, currency) --[ way out ]--> a spendable endpoint

Each seam has **two halves**, and both are tested with a deliberate mismatch:

* the **venue**, which nothing else guards -- two hryvnia venues are identical to a currency
  check, and a way in landing at the wrong one funds a purchase with money that never arrived;
* the **currency**, which is the half a reader assumes is the whole check.

Four cases, and each asserts that the refusal **names both sides**. A refusal saying only
"the seam does not chain" would leave the reader to work out which declaration to open, and a
refusal naming only the side it found first would send them to the wrong one.

What must never happen is the fifth outcome: a figure. Bridging either gap means a transfer or
a conversion nobody declared, at a rate nobody quoted, and it is the single most tempting
fabrication in this feature because the two declarations sit next to each other and look
adjacent.
"""

from __future__ import annotations

import pytest

from terezy.core.decision.tuple_outcome import Registries, evaluate
from terezy.core.primitives.money import Money
from terezy.core.results.tuple import SeamDoesNotChain, Tuple, TupleOutcome
from terezy.core.routes.path import ComposedExit, DeclaredExit, FundingPath
from tests import tuple_registries as fixtures


def _evaluated(
    registries: Registries, candidate: Tuple | None = None, *, amount: Money | None = None
) -> object:
    return evaluate(
        candidate if candidate is not None else fixtures.hurdle_tuple(),
        amount=fixtures.AMOUNT if amount is None else amount,
        horizon=fixtures.HORIZON,
        as_of=fixtures.AS_OF,
        continuation=fixtures.HOLD_AS_CASH,
        registries=registries,
    )


def _refused(
    registries: Registries, candidate: Tuple | None = None, *, amount: Money | None = None
) -> SeamDoesNotChain:
    outcome = _evaluated(registries, candidate, amount=amount)
    assert isinstance(outcome, SeamDoesNotChain), outcome
    return outcome


class TestTheShippedTupleChains:
    """The control. Without it, every assertion below could pass for the wrong reason."""

    def test_the_declared_domestic_round_trip_produces_an_outcome(self) -> None:
        assert isinstance(_evaluated(fixtures.shipped()), TupleOutcome)


class TestTheFirstSeamTheWayInAndThePurchase:
    """The way in must end **where and in the currency** the purchase begins."""

    def test_a_way_in_landing_at_another_venue_is_refused_naming_both(self) -> None:
        # The instrument is declared bought at `inzhur`; the way in still ends at `inzhur`.
        # Moving the *access* declaration to `monobank_uah` -- a venue that also holds UAH,
        # so the currency check passes -- is the venue half on its own.
        refusal = _refused(
            fixtures.with_access(fixtures.shipped(), fixtures.OVDP, bought_at="monobank_uah")
        )
        assert refusal.seam == "route_in_to_purchase"
        assert refusal.left == "inzhur/UAH"
        assert refusal.right == "monobank_uah/UAH"
        assert "inzhur" in refusal.reason
        assert "monobank_uah" in refusal.reason

    def test_a_way_in_arriving_in_another_currency_is_refused_naming_both(self) -> None:
        # `binance` holds both currencies, so a dollar route into it is a well-formed
        # declaration: the venue half of the seam matches and only the currency half does not.
        # Nothing bridges the gap -- the instrument is bought in hryvnia and the money that
        # arrived is dollars, and a conversion here would be an invented leg at an invented
        # rate.
        registries = fixtures.with_new_route(
            fixtures.shipped(),
            fixtures.route(
                "test_deel_to_binance",
                origin="deel",
                destination="binance",
                direction="inbound",
                currency=fixtures.Currency.USD,
            ),
        )
        registries = fixtures.with_access(registries, fixtures.OVDP, bought_at="binance")
        candidate = Tuple(
            instrument_id=fixtures.OVDP,
            stream_id="contract_usd",
            route_in=FundingPath(
                destination_id="binance",
                stream_id="contract_usd",
                route_id="test_deel_to_binance",
            ),
            exit_terms=fixtures.HOLD_TO_MATURITY,
            route_out=DeclaredExit(route_id=fixtures.DOMESTIC_OUT),
        )
        refusal = _refused(
            registries,
            candidate,
            amount=fixtures.Money(1_000.0, fixtures.Currency.USD, fixtures.prov.EMPTY),
        )
        assert refusal.seam == "route_in_to_purchase"
        assert refusal.left == "binance/USD"
        assert refusal.right == "binance/UAH"
        assert "USD" in refusal.reason
        assert "UAH" in refusal.reason


class TestTheSecondSeamTheProceedsAndTheWayOut:
    """The instrument's exit must produce a balance **where and in the currency** the way out
    begins."""

    def test_proceeds_landing_at_another_venue_are_refused_naming_both(self) -> None:
        # The declared way out departs from `inzhur`. Saying the proceeds land at
        # `monobank_uah` -- again a UAH venue, so only the venue half differs -- is the case
        # feature 004 walked anyway: the exit chain would be priced with money it never had.
        registries = fixtures.with_access(
            fixtures.shipped(), fixtures.OVDP, proceeds_to="monobank_uah"
        )
        # `monobank_uah` in hryvnia IS a declared spendable endpoint, so the derived way out
        # would be EXIT_BY_IDENTITY and no seam would be crossed at all. Naming the chain
        # explicitly is what puts the two declarations back in contact.
        refusal = _refused(
            registries,
            fixtures.hurdle_tuple(route_out=DeclaredExit(route_id=fixtures.DOMESTIC_OUT)),
        )
        assert refusal.seam == "proceeds_to_route_out"
        assert refusal.left == "monobank_uah/UAH"
        assert refusal.right == "inzhur/UAH"
        assert fixtures.DOMESTIC_OUT in refusal.reason

    def test_proceeds_in_another_currency_are_refused_naming_both(self) -> None:
        # The exit route departs `inzhur` in hryvnia. A declared way out from the same venue
        # in dollars does not meet it, and the venue half matching is exactly what makes this
        # the case a venue-only check would miss.
        registries = fixtures.shipped()
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_usd_out_of_inzhur",
                origin="inzhur",
                destination="monobank_uah",
                direction="exit",
                currency=fixtures.Currency.USD,
            ),
        )
        refusal = _refused(
            registries,
            fixtures.hurdle_tuple(route_out=DeclaredExit(route_id="test_usd_out_of_inzhur")),
        )
        assert refusal.seam == "proceeds_to_route_out"
        assert refusal.left == "inzhur/UAH"
        assert refusal.right == "inzhur/USD"
        assert "UAH" in refusal.reason
        assert "USD" in refusal.reason

    def test_an_asserted_exit_by_identity_that_is_not_spendable_is_refused(self) -> None:
        # `EXIT_BY_IDENTITY` is the bare claim *there is nothing to do*, and its whole content
        # is a statement about the far end. Unchecked it produced feature 004's defect in its
        # purest form: a complete round trip for money sitting where it cannot be spent.
        refusal = _refused(
            fixtures.shipped(), fixtures.hurdle_tuple(route_out=fixtures.EXIT_BY_IDENTITY)
        )
        assert refusal.seam == "proceeds_to_route_out"
        assert refusal.left == "inzhur/UAH"
        assert refusal.right == "a declared spendable endpoint"
        assert "monobank_uah" in refusal.reason


class TestNoSeamIsBridged:
    """Whatever the refusal says, what it must never do is produce a figure."""

    @pytest.mark.parametrize(
        "registries",
        [
            pytest.param(
                fixtures.with_access(fixtures.shipped(), fixtures.OVDP, bought_at="binance"),
                id="purchase at a venue the way in does not reach",
            ),
            pytest.param(
                fixtures.with_access(fixtures.shipped(), fixtures.OVDP, proceeds_to="binance"),
                id="proceeds at a venue the way out does not depart from",
            ),
        ],
    )
    def test_a_broken_seam_never_yields_an_outcome(self, registries: Registries) -> None:
        assert not isinstance(_evaluated(registries), TupleOutcome)

    def test_a_composed_way_out_is_anchored_at_its_head_like_a_single_one(self) -> None:
        # 004's own lesson, restated where this feature can repeat it: the anchor is on the
        # *first* segment of the chain, so a two-segment way out starting somewhere the money
        # is not is refused exactly as a one-segment one is.
        registries = fixtures.shipped()
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_binance_to_monobank",
                origin="binance",
                destination="monobank_uah",
                direction="exit",
            ),
        )
        registries = fixtures.with_new_route(
            registries,
            fixtures.route(
                "test_monobank_to_monobank",
                origin="monobank_uah",
                destination="monobank_uah",
                direction="exit",
            ),
        )
        refusal = _refused(
            registries,
            fixtures.hurdle_tuple(
                route_out=ComposedExit(
                    segments=("test_binance_to_monobank", "test_monobank_to_monobank")
                )
            ),
        )
        assert refusal.left == "inzhur/UAH"
        assert refusal.right == "binance/UAH"
