"""There is exactly **one** rule for putting a number on a diagram, and no second one.

**SC-006** and **FR-022**, which was added on external review after the review found that
SC-006's original "byte for byte" claim was undefined as written: results carry ``float``,
the project's canonical float form is hexadecimal (``METHODOLOGY`` §12.2), and no
human-readable decimal rendering rule existed anywhere. So "the diagram shows the result's
figure" compared diagram text against a form nobody had defined.

The fix is a rule on the model of the single project tolerance
(``core.primitives.tolerance``): defined in one place, imported everywhere, and a second one
is a **defect** rather than a preference. This module is the executable half of that.

**Three claims, and the third is the one that keeps the other two true.**

1. The rule renders a fixed two decimals, and it **rounds** -- ``FR-008`` permits exactly
   this one transformation and no other, which is why the diagram is a picture and not the
   audit trail.
2. ``numbers.py`` itself contains exactly **one** float format spec, so the two public
   functions cannot drift apart.
3. **Nothing else in the package formats a float at all.** That is a grep, because the
   failure mode is not a wrong number -- it is a *second* rounding, one call site formatted
   to three decimals because two looked coarse, and no assertion about a figure would ever
   catch it. The scan is proved able to fail, on a planted violation, because a scan that
   cannot fail protects nothing.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from terezy.api.diagrams import numbers
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from tests.source_scan import executable_source, strip_prose

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DIAGRAMS_ROOT = REPO_ROOT / "src" / "terezy" / "api" / "diagrams"
THE_RULE = DIAGRAMS_ROOT / "numbers.py"

FLOAT_FORMAT_SPEC = re.compile(r":\.[0-9{]")
"""An f-string format spec that fixes decimal places -- ``:.2f`` or ``:.{PLACES}f``.

The only place in this package one may appear is :data:`THE_RULE`.
"""

A_SECOND_RULE = re.compile(
    r":\.[0-9{]"  # an f-string format spec
    r"|\bround\("  # the builtin
    r"|\bformat\("  # the builtin, or str.format
    r"|%\.[0-9]"  # printf-style
    r"|\bDecimal\b"  # a second numeric tower, quantised its own way
    r"|__format__"  # the dunder, reached for when the above are grepped out
)
"""Every shape a second number-rendering rule has taken in a Python codebase."""


class TestTheRuleItself:
    """Two decimals, and the rounding said out loud rather than discovered later."""

    def test_a_percentage_is_a_fraction_rendered_as_fixed_two_decimals(self) -> None:
        """A fraction in, a percentage out. ``3/45`` is §4.3.1's one-way P2P cost."""
        assert numbers.percent(3.0 / 45.0) == "6.67%"
        assert numbers.percent(5.5 / 45.0) == "12.22%"
        assert numbers.percent(0.125) == "12.50%"
        assert numbers.percent(0.0) == "0.00%"

    def test_an_amount_is_fixed_two_decimals_with_its_currency_code(self) -> None:
        """The code, never a symbol: UAH and USD must never look interchangeable."""
        assert numbers.amount(Money(1234.5678, Currency.UAH, prov.EMPTY)) == "1234.57 UAH"
        assert numbers.amount(Money(0.0, Currency.USD, prov.EMPTY)) == "0.00 USD"

    def test_the_rule_rounds_and_the_rounding_is_visible(self) -> None:
        """FR-008 permits this one transformation, so it is asserted rather than assumed.

        The arithmetic, checked by hand against Python's round-half-even on the *double*:
        ``0.125`` is exactly representable and rounds to even -> ``0.12``; ``0.135`` is
        really ``0.13500000000000001`` and rounds up -> ``0.14``. Both are here so that a
        future "fix" to half-up has to change a test that states what it is changing.
        """
        assert numbers.amount(Money(0.125, Currency.UAH, prov.EMPTY)) == "0.12 UAH"
        assert numbers.amount(Money(0.135, Currency.UAH, prov.EMPTY)) == "0.14 UAH"
        assert numbers.amount(Money(1e-9, Currency.UAH, prov.EMPTY)) == "0.00 UAH"

    def test_a_rounded_away_negative_keeps_its_sign(self) -> None:
        """``-0.00 UAH`` rather than ``0.00 UAH``, deliberately.

        A tiny negative amount is a real fact -- fees exceeding the amount is predecessor
        defect B13's territory -- and normalising the sign away would be the renderer
        deciding a number's meaning. The rounding is visible; the sign is not lost to it.
        """
        assert numbers.amount(Money(-0.001, Currency.UAH, prov.EMPTY)) == "-0.00 UAH"
        assert numbers.percent(-1e-9) == "-0.00%"

    def test_the_decimal_places_are_declared_once_and_are_what_the_rule_uses(self) -> None:
        assert numbers.DECIMAL_PLACES == 2
        assert len(numbers.percent(1.0).removesuffix("%").split(".")[1]) == numbers.DECIMAL_PLACES


class TestThereIsOnlyOneRule:
    """The grep. This is the assertion FR-022 actually asks for."""

    def test_the_rule_module_holds_exactly_one_float_format_spec(self) -> None:
        """Two would let ``percent`` and ``amount`` drift apart inside the one module."""
        found = FLOAT_FORMAT_SPEC.findall(executable_source(THE_RULE))
        assert len(found) == 1, (
            f"numbers.py contains {len(found)} float format specs, not one. Both public "
            "functions must render through the same private helper, or the single rule is "
            "two rules sharing a file"
        )

    def test_no_other_module_in_the_package_formats_a_float(self) -> None:
        """The failure mode is a third decimal at one call site, called a fix."""
        offenders: dict[str, list[str]] = {}
        for path in sorted(DIAGRAMS_ROOT.rglob("*.py")):
            if path == THE_RULE:
                continue
            found = A_SECOND_RULE.findall(executable_source(path))
            if found:
                offenders[path.name] = found
        assert not offenders, (
            f"a second number-rendering rule exists: {offenders}. Every figure on every "
            "diagram goes through terezy.api.diagrams.numbers (FR-022); an inline format at "
            "a call site is a defect, not a preference"
        )

    def test_the_package_has_modules_for_the_scan_to_have_looked_at(self) -> None:
        """A scan over an empty directory passes and proves nothing."""
        scanned = {path.name for path in DIAGRAMS_ROOT.rglob("*.py")} - {THE_RULE.name}
        assert len(scanned) >= 4, scanned

    @pytest.mark.parametrize(
        "planted",
        [
            'def f(x: float) -> str:\n    return f"{x:.3f}"\n',
            "def f(x: float) -> float:\n    return round(x, 2)\n",
            'def f(x: float) -> str:\n    return "{:.2f}".format(x)\n',
            'def f(x: float) -> str:\n    return "%.2f" % x\n',
            "from decimal import Decimal\n\n\ndef f(x: float) -> object:\n    return Decimal(x)\n",
            "def f(x: float) -> str:\n    return x.__format__('.2f')\n",
        ],
    )
    def test_the_scan_would_catch_a_planted_second_rule(self, planted: str) -> None:
        """A scan that can never fail protects nothing, so prove each shape is caught."""
        assert A_SECOND_RULE.search(strip_prose(planted))

    def test_prose_about_the_rule_is_not_itself_a_second_rule(self) -> None:
        """Every docstring in this package has to be able to say what the rule is."""
        prose = '"""A module about :.2f, round( and format( -- all prose."""\nX: int = 1\n'
        assert not A_SECOND_RULE.search(strip_prose(prose))
