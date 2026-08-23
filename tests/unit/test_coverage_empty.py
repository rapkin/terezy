"""An empty registry dimension is a typed outcome, never an empty report. **SC-013.**

FR-020: *an empty registry dimension -- no streams, no venues, no routes -- MUST produce a
typed outcome naming which dimension is empty. The report MUST never be an empty result a
caller could mistake for full coverage.*

This is predecessor defect **B10** in its natural habitat. An empty coverage report has no
not-ready verdicts in it, which is indistinguishable from a registry where everything is
comparable -- and it is the *more* flattering of the two readings, which is why it is the one
that gets believed. So there is no input for which ``coverage`` returns a report with no
verdicts: the empty cases return :class:`RegistryDimensionEmpty` instead, which is unrelated to
:class:`CoverageReport` and therefore cannot be read as one.

⚙ **``spendable`` is named alongside the three FR-020 lists, and FR-020 does not list it.**
The widening is recorded in plan.md's Complexity Tracking and it is a widening towards honesty:
an empty spendable list makes *every* declared exit fail the spendable test, so the report would
be full of deficit-3 verdicts -- confident, wrong, and produced from a forgotten line. The
loader refuses an empty list and an empty directory too, so this typed outcome only fires for a
direct core call. The tests below are that direct core call.

The last case is research.md D14's: a declared regime carrying the id the report reserves for
the implicit one. Refused rather than shadowed, because FR-015's *"MUST say that this is what it
did"* is not satisfied by a block the owner cannot tell apart from his own.
"""

from __future__ import annotations

import pytest

from terezy.core.results.coverage import (
    IMPLICIT_REGIME_ID,
    CoverageReport,
    RegistryDimensionEmpty,
    ReservedRegimeId,
)
from terezy.core.routes.coverage import coverage
from tests.coverage_registries import UAH, USD, keyed, regime, route, spendable, stream, venue

VENUES = keyed([venue("mono", UAH), venue("broker", USD)])
STREAMS = keyed([stream("salary_uah", UAH, "mono")])
ROUTES = keyed(
    [
        route(
            "in_mono_broker",
            origin="mono",
            destination="broker",
            direction="inbound",
            from_ccy=UAH,
            to_ccy=USD,
        ),
        route(
            "out_broker_mono",
            origin="broker",
            destination="mono",
            direction="exit",
            from_ccy=USD,
            to_ccy=UAH,
        ),
    ]
)
SPENDABLE = spendable(("mono", UAH))


def test_the_full_registry_produces_a_report() -> None:
    """The control. Every case below removes exactly one thing from this."""
    produced = coverage(
        venues=VENUES, streams=STREAMS, routes=ROUTES, regimes={}, spendable=SPENDABLE
    )
    assert isinstance(produced, CoverageReport)
    assert produced.regimes[0].verdicts


@pytest.mark.parametrize(
    ("dimension", "kwargs"),
    [
        ("venues", {"venues": {}}),
        ("streams", {"streams": {}}),
        ("routes", {"routes": {}}),
        ("spendable", {"spendable": frozenset()}),
    ],
)
def test_each_empty_dimension_is_a_typed_outcome_naming_it(
    dimension: str, kwargs: dict[str, object]
) -> None:
    """SC-013, FR-020. Named, not counted, and not an empty report."""
    produced = coverage(
        **{  # type: ignore[arg-type]
            "venues": VENUES,
            "streams": STREAMS,
            "routes": ROUTES,
            "regimes": {},
            "spendable": SPENDABLE,
            **kwargs,
        }
    )
    assert isinstance(produced, RegistryDimensionEmpty)
    assert produced.dimensions == (dimension,)
    assert dimension in produced.reason


def test_every_empty_dimension_is_named_not_only_the_first() -> None:
    """Four empty dimensions, four names, one run.

    Reporting the first one found would make an owner with an empty data root fix four things
    in four runs, each time learning one more fact he could have been told at the start.
    """
    produced = coverage(venues={}, streams={}, routes={}, regimes={}, spendable=frozenset())
    assert isinstance(produced, RegistryDimensionEmpty)
    assert produced.dimensions == ("routes", "spendable", "streams", "venues")


def test_an_empty_regimes_mapping_is_not_a_refusal() -> None:
    """FR-015: no declared regime is the *implicit* regime, which is a report, not a hole.

    Stated as its own test because the four dimensions above and this fifth mapping look
    identical at a call site, and the difference is the whole of D14: the owner not declaring
    a regime is a legitimate registry, while the owner declaring no venues is a mistake.
    """
    produced = coverage(
        venues=VENUES, streams=STREAMS, routes=ROUTES, regimes={}, spendable=SPENDABLE
    )
    assert isinstance(produced, CoverageReport)


def test_a_declared_regime_carrying_the_reserved_id_is_refused() -> None:
    """research.md D14. Shadowing the owner's own regime would be worse than refusing.

    The implicit id is parenthesised precisely so it cannot collide by accident, and a
    collision is therefore a deliberate act or a copy-paste -- neither of which the report can
    resolve on the owner's behalf. Refusing names the id; shadowing would produce a block whose
    ``source`` said ``declared`` while its contents were the report's own, or the reverse.
    """
    produced = coverage(
        venues=VENUES,
        streams=STREAMS,
        routes=ROUTES,
        regimes=keyed([regime(IMPLICIT_REGIME_ID, *ROUTES)]),
        spendable=SPENDABLE,
    )
    assert isinstance(produced, ReservedRegimeId)
    assert produced.regime_id == IMPLICIT_REGIME_ID
    assert IMPLICIT_REGIME_ID in produced.reason


def test_a_regime_naming_an_undeclared_route_raises() -> None:
    """On ``regimes.routes_in_force``'s precedent, and for its reason.

    The resolver refuses this at load and can name the file and the row; reaching core with it
    means that check was bypassed, which is a programmer error rather than a fact about the
    money -- so it raises rather than returning a typed outcome. A typed outcome here would
    invite callers to keep building incoherent regimes and read the answer as coverage.
    """
    with pytest.raises(KeyError, match="not declared"):
        coverage(
            venues=VENUES,
            streams=STREAMS,
            routes=ROUTES,
            regimes=keyed([regime("wartime", "in_mono_broker", "no_such_route")]),
            spendable=SPENDABLE,
        )
