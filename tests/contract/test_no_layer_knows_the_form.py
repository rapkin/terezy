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

⚙ **One escape is not hypothetical and is in the tree**: ``AmountsAsDeclared``, in
`core/primitives/conventions.py`, is a form-shaped name that `core/results/canonical.py`
matches on. FR-012's substance holds -- it renders a statement it was handed and moves no
money, and FR-016 *requires* the encoder to tell the two statements apart -- but the scan
cannot see it, and three docstrings on this branch call `core.instruments.terms` "the one
place in ``src/`` that matches on which form a declaration is in" without qualifying it.
Recorded here so the list of what this scan misses matches the tree rather than only the
hypotheticals (2026-08-30).

⚙ **And one escape is closed below rather than listed.** ``day_count`` is the one declared
term **both** forms carry, so a sealed module that stopped asking `day_count_of` and read
``declaration.terms.day_count`` directly would pass `mypy`, `lint-imports` and this scan --
FR-002's promise that *the type checker enumerates the sites that must change* covers four
of the five forbidden terms and not that one. It is the exact regression FR-011a exists to
prevent, so it gets an assertion of its own.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from terezy.core.instruments import registry
from terezy.core.instruments import terms as instrument_terms
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
    """A scan of nothing passes forever, so the modules it must reach are named.

    Every site this feature touched inside the seal: FR-011a's three, FR-016's corrected
    docstrings, and FR-023's per-declaration exclusions. Named rather than counted -- a
    count over its own list is the staleness shape this branch corrected six times."""
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


READS_A_SHARED_TERM = re.compile(r"terms\.(?:day_count|face_value)(?!_of)\b")
"""The reads the type checker cannot catch, because **both** forms declare the field.

``BondTerms`` and ``EnumeratedTerms`` share three fields. Two of them are *terms*:

* ``day_count`` -- a convention of computation, which every figure that annualises needs;
* ``face_value`` -- the redemption amount a unit is declared to repay.

Reading either through ``declaration.terms`` type-checks against both forms, so nothing in
the toolchain objects and the site has silently stopped asking the declaration, which is
what FR-011a requires of it. ``day_count_of`` and ``face_value_of`` are the only permitted
spellings inside the seal, and the lookahead is what lets them through -- they end in the
same characters.

⚙ **``face_value`` is here because the read was real, not hypothetical.** Until the fix
round, ``core/results/project.py`` read ``declaration.terms.face_value`` directly under a
docstring justifying it in exactly these words -- *both forms state one and mean the same
thing by it* -- and that read **is** defect F2: it measured a purchase against the nominal
face and reported a discount of everything a previous holder had already been repaid. The
read was removed and the seal then closed over the *other* shared term only, which would
have let F2 walk back in past every gate.

⚙ **``provenance`` is the third shared field and is deliberately not sealed.** It is the
citation rather than a term: it means the same thing in both forms, carries no form-specific
reading, and a results module reading it is what makes a figure traceable -- ``_at_purchase``
reads it on purpose.
"""


def test_no_sealed_module_reads_a_term_both_forms_carry() -> None:
    offenders = {
        path.relative_to(SOURCE_ROOT).as_posix()
        for path in _sealed_files()
        if READS_A_SHARED_TERM.search(source_scan.executable_source(path))
    }
    assert not offenders, (
        "a sealed module reads a term both declaration forms carry directly instead of "
        f"asking for it (FR-011a): {offenders}. It type-checks against either form, which "
        "is exactly why the union does not catch it -- ask `instrument_terms.day_count_of` "
        "or `face_value_of`, and for what a *purchase* is measured against, "
        "`principal_returned`"
    )


@pytest.mark.parametrize(
    "planted",
    [
        "year_fraction = conventions.day_count(terms.day_count)\n",
        "if declaration.terms.day_count == '30/360':\n",
        # The F2 read, verbatim from `project.py` before the fix round removed it.
        "at_face = money.scale_sourced(declaration.terms.face_value, holding.quantity)\n",
        "currency = declaration.terms.face_value.currency\n",
    ],
)
def test_that_scan_would_catch_the_read_it_forbids(planted: str) -> None:
    assert READS_A_SHARED_TERM.search(planted), planted


@pytest.mark.parametrize(
    "asking",
    [
        "year_fraction = conventions.day_count(instrument_terms.day_count_of(terms))\n",
        "face = instrument_terms.face_value_of(declaration.terms)\n",
        "back = instrument_terms.principal_returned(terms, bought_on=holding.purchased_on)\n",
    ],
)
def test_and_would_let_the_question_through(asking: str) -> None:
    """Asking the declaration must stay permitted (FR-011a), and the two ``_of`` spellings
    end in the same characters as the fields they replace -- which is what the lookahead is
    for and what would otherwise make this seal unusable."""
    assert not READS_A_SHARED_TERM.search(asking), asking


def test_the_questions_the_refusal_names_all_exist() -> None:
    """A refusal that names an answer which does not exist sends a reader nowhere."""
    for question in ("day_count_of", "face_value_of", "principal_returned"):
        assert hasattr(instrument_terms, question), question


def test_the_instrument_layer_is_deliberately_outside_the_seal() -> None:
    """The one place that matches on a *declaration's* form is `core.instruments.terms`, and
    it has to be: somebody must answer the question, and answering it once is what stops four
    modules deciding it separately.

    ⚙ Not the only `match` on a form-shaped **type** in `src/` -- see the module docstring's
    note on `AmountsAsDeclared`, which `core.results.canonical` matches on because FR-016
    requires the two conventions statements to be told apart. That one renders a value it was
    handed and moves no money."""
    answering = source_scan.executable_source(SOURCE_ROOT / "core" / "instruments" / "terms.py")
    assert "EnumeratedTerms" in answering
    assert "core/instruments" not in SEALED
