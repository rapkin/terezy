"""The exact Fisher relation, and nothing else in this module.

    real = (1 + nominal) / (1 + inflation) - 1

**Not** ``nominal - inflation``. FR-008 says so in as many words, and the reason is
arithmetic rather than taste: at 80% annual inflation -- which Ukraine's own series reaches
inside a year in the early 1990s -- the approximation is twenty-eight percentage points
wrong, which is larger than most of the differences this tool exists to detect. A figure that
wrong would still look like a plausible real rate, which is what makes it dangerous rather
than merely inaccurate.

**The module holds one function on purpose.** The approximation is what a reader will reach
for unless stopped, because it is the version they were taught, and the thing that stops them
is not a comment. Keeping the conversion in a module with no other content means there is one
place to look, one place to change, and nothing to hide an "estimate" beside;
``tests/contract/test_no_subtraction_approximation.py`` scans the source of this module and
its neighbours and fails on any subtraction whose right-hand side is not a plain number.

**Both rates must be measured over the same span.** This function has no idea what span that
is -- it takes two numbers -- so the caller annualises first
(``core.inflation.series.annualised``). Deflating an annual yield by six months of inflation
would flatter the real return by roughly half the inflation, and nothing here could detect it.

**Nothing is clamped.** A window in which prices fell yields a real rate *above* the nominal
one, and inflation above the nominal rate yields a negative real rate. Both are valid
observations and both are reported as the numbers they are (Principle IV, "no silent
clamping"): a negative real return is the finding, not an error to be tidied away.
"""

from __future__ import annotations


def deflate(*, nominal: float, inflation: float) -> float:
    """A nominal rate as the real rate it corresponds to, given inflation over the same span.

    Keyword-only, both of them. The two arguments are the same type, mean opposite things,
    and swapping them produces a plausible number: at a nominal 15% and inflation of 5% the
    swap gives -8.7% instead of +9.5%, and nothing downstream could tell. A positional call
    site is one edit away from that, so there are none.

    Raises ``ValueError`` when inflation is exactly ``-1`` -- prices having fallen to nothing.
    A declared index value is strictly positive and a declared assumed rate is strictly above
    ``-1``, both checked at the data boundary, so the denominator cannot reach zero from
    declared data and reaching here at ``-1`` means that validation was bypassed. Refused
    rather than allowed to raise ``ZeroDivisionError``, whose message says nothing about
    money.
    """
    if 1.0 + inflation == 0.0:
        raise ValueError(
            "cannot deflate by an inflation rate of exactly -1: that is prices having fallen "
            "to nothing, and every real rate against it would be infinite. Declared index "
            "values are strictly positive and declared assumed rates strictly above -1, both "
            "checked at the data boundary, so reaching here means that check was bypassed."
        )
    return (1.0 + nominal) / (1.0 + inflation) - 1.0
