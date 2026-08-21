"""C5 -- values in different currencies can never be combined.

Constitution Principle IV ("Money is float64, carried in a currency-tagged immutable
record so values in different currencies can never be silently combined") and FR-007
("Any attempt to add, subtract or compare monetary amounts of different currencies MUST
fail as an error. Implicit conversion MUST NOT occur anywhere.").

Property-based rather than example-based on purpose: the requirement is about *every*
pair of amounts, and a handful of examples would only prove that the cases someone
thought of are guarded. Tracked as C5 in ``docs/REQUIRED_TESTS.md``.

A currency mismatch is one of the few places the constitution asks for a ``raise``
rather than a typed failure result: mixing UAH with USD is a programmer error, not a
business outcome, so it must stop the run instead of flowing into a result.
"""

from __future__ import annotations

from datetime import date

import pytest
from hypothesis import given
from hypothesis import strategies as st

from terezy.core.errors import CurrencyMismatchError
from terezy.core.primitives import money, provenance
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money

_REF = provenance.of(
    [
        provenance.SourceRef(
            id="test/currency_safety",
            citation="synthetic test input",
            retrieved_on=date(2026, 8, 21),
            verified_on=date(2026, 8, 21),
        )
    ]
)

_AMOUNTS = st.floats(
    min_value=-1e9,
    max_value=1e9,
    allow_nan=False,
    allow_infinity=False,
    allow_subnormal=False,
)


def _money(amount: float, currency: Currency) -> Money:
    return Money(amount, currency, _REF)


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_add_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.add(_money(left, Currency.UAH), _money(right, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.add(_money(left, Currency.USD), _money(right, Currency.UAH))


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_subtract_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.sub(_money(left, Currency.UAH), _money(right, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.sub(_money(left, Currency.USD), _money(right, Currency.UAH))


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_compare_across_currencies_always_raises(left: float, right: float) -> None:
    with pytest.raises(CurrencyMismatchError):
        money.compare(_money(left, Currency.UAH), _money(right, Currency.USD))


@pytest.mark.invariant
@given(amounts=st.lists(_AMOUNTS, min_size=1, max_size=6))
def test_total_rejects_a_foreign_amount_anywhere_in_the_sum(amounts: list[float]) -> None:
    """A single foreign amount in a list is enough to stop the sum.

    This is the aggregation case, and it is the one that matters: a mismatch guarded
    only on the binary operation would still let a mixed list through if ``total`` had
    its own accumulation loop.
    """
    items = [_money(amount, Currency.UAH) for amount in amounts]
    items.append(_money(1.0, Currency.USD))
    with pytest.raises(CurrencyMismatchError):
        money.total(items, Currency.UAH)


@pytest.mark.invariant
@given(left=_AMOUNTS, right=_AMOUNTS)
def test_same_currency_combines_and_keeps_the_currency(left: float, right: float) -> None:
    """The mismatch guard must not be so eager that matching currencies fail."""
    result = money.add(_money(left, Currency.UAH), _money(right, Currency.UAH))
    assert result.currency is Currency.UAH


@pytest.mark.invariant
def test_no_conversion_function_exists() -> None:
    """There is nowhere to convert, so nothing can convert implicitly.

    FR-007 forbids implicit conversion *anywhere*. The strongest available check is
    that the one module permitted to combine money exposes no conversion at all: no
    rate argument, no ``convert``, no ``in_currency``. When FX lands it will arrive as
    an explicit, dated, provenance-carrying operation in its own module -- and this
    assertion will have to be revisited deliberately rather than by accident.
    """
    public_names = {name for name in vars(money) if not name.startswith("_")}
    forbidden = {"convert", "to_currency", "in_currency", "exchange", "fx", "rate"}
    assert not (public_names & forbidden)

    combining = {name for name in public_names if name in {"add", "sub", "total", "compare"}}
    assert combining == {"add", "sub", "total", "compare"}
