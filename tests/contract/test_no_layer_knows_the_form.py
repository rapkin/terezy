"""SC-003: no layer below the instruments knows there are two declaration forms.

FR-012. The ledger, the tax engine, the decision layer and the results -- **including
`core/results/project.py`** -- may not name the enumerated form, and may not test which
form a declaration is in order to decide what to compute. Asking a declaration a question
both forms answer is not naming it and stays permitted; that is FR-011a's delegation, and
it is what keeps this scan passing.

If the property could not be met, the correct response would be to stop and report it: a
form the tax engine or the ranking has to know about is a second instrument concept wearing
one interface, which is what the four-interface limit of constitution Principle II protects
against.

**What this scan does not catch, stated so it is not read as complete.** It catches the
usual spellings of a form test only because they name the type -- ``isinstance(...)``,
``case EnumeratedTerms()``. A form test spelled without the name passes it:
``terms.schedule is not None``, a ``case BondTerms(): ... case _:`` pair,
``if declaration.instrument_class != "fixed_income"``. That residual is covered by the
delegation being *sufficient* -- there is nothing those spellings would buy that
`core.instruments.terms` does not already answer -- and by review. It is recorded here
rather than left for a reader to discover, because a scan believed complete is the one
nobody adds a second check beside.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from terezy.core.instruments import registry
from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCE_ROOT = REPO_ROOT / "src" / "terezy"

SEALED = (
    "core/ledger",
    "core/tax",
    "core/decision",
    "core/results",
)
"""The packages FR-012 seals, by package rather than by file.

A list of files goes stale silently: a module added to `core/results` tomorrow would be
outside a file list and inside the requirement.
"""

NAMES = (
    r"Enumerated[A-Za-z]*",
    r"ScheduledPayment",
    r"PaymentKind",
    r"PAYMENT_KINDS",
    re.escape(registry.ENUMERATED_SCHEDULE),
    r"ENUMERATED_SCHEDULE",
    r"enumerated[ _](?:instrument|declaration|bond|form|schedule|terms|payments?|row)",
)
"""Every spelling of the form: the records, the closed set of payment labels, the declared
class name, and the word in prose.

⚙ The prose alternative is deliberately **not** the bare word. "the bound in force when
these candidates were enumerated" and "matched on the declared prose rather than on an
enumerated code" are ordinary English that predate this feature, and a scan flagging them
would be a scan somebody turns off. What is forbidden is naming *this* form, so the pattern
requires the noun that would follow it.
"""

PATTERN = re.compile("|".join(NAMES))


def _sealed_files() -> list[Path]:
    return sorted(path for package in SEALED for path in (SOURCE_ROOT / package).rglob("*.py"))


def test_no_sealed_module_names_the_enumerated_form() -> None:
    """Prose counts. FR-012 forbids *naming* it, and a docstring explaining a function by
    saying "for an enumerated instrument" is a claim about a declaration form that the
    module is supposed not to know exists."""
    offenders = {
        str(path.relative_to(SOURCE_ROOT)): sorted(set(PATTERN.findall(path.read_text("utf-8"))))
        for path in _sealed_files()
        if PATTERN.search(path.read_text("utf-8"))
    }
    assert not offenders, (
        "a module under the ledger, the tax engine, the decision layer or the results names "
        f"the enumerated declaration form (FR-012): {offenders}. Ask the declaration a "
        "question both forms answer -- see core.instruments.terms -- rather than learning "
        "that there are two."
    )


def test_the_scan_reaches_the_modules_that_could_hold_such_a_branch() -> None:
    """A scan of nothing passes forever. These are the three sites FR-011a names and the
    two FR-016 corrects, so the scan is worthless if it does not read them."""
    walked = {path.relative_to(SOURCE_ROOT).as_posix() for path in _sealed_files()}
    assert {
        "core/ledger/seeds.py",
        "core/decision/tuple_outcome.py",
        "core/results/project.py",
        "core/results/schedule.py",
        "core/results/canonical.py",
        "core/results/hurdle.py",
    } <= walked


def test_the_scan_would_catch_a_module_that_learned_the_form(tmp_path: Path) -> None:
    """Falsifiability. Planted violations of each shape, and a negative case proving the
    scan is not simply matching everything."""
    for planted in (
        "if isinstance(declaration.terms, EnumeratedTerms):\n    pass\n",
        "match terms:\n    case EnumeratedTerms():\n        pass\n",
        'if declaration.instrument_class == "enumerated_schedule":\n    pass\n',
        '"""The statement a row makes for an enumerated instrument."""\n',
    ):
        assert PATTERN.search(planted), planted
    assert not PATTERN.search(
        "conventions = instrument_terms.conventions_of(declaration.terms)\n"
    ), "asking a declaration a question both forms answer must stay permitted (FR-011a)"


def test_the_instrument_layer_is_deliberately_outside_the_seal() -> None:
    """The one place that matches on the form is `core.instruments.terms`, and it has to
    be: somebody must answer the question, and answering it once is what stops four
    modules deciding it separately."""
    answering = source_scan.executable_source(SOURCE_ROOT / "core" / "instruments" / "terms.py")
    assert "EnumeratedTerms" in answering
    assert "core/instruments" not in SEALED
