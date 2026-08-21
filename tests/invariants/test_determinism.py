"""C4 -- the same inputs produce the same bits, and a different input produces different bits.

Constitution Principle III: *"Same scenario + same data snapshot ⇒ identical results."*
SC-006 states how it is checked -- *"two runs on identical inputs produce identical results,
verified by comparing a digest of the complete output"* -- and FR-012 requires the digest to
sit in a manifest alongside the inputs and their versions. This suite is the compliance test
for that clause and may not be skipped, marked expected-to-fail, or deleted without a
constitutional amendment.

**The digest asserts bit-identity, and is deliberately stricter than the project
tolerance** (research.md D5). The tolerance exists because hand-computed arithmetic and
float arithmetic differ; determinism means the same code on the same inputs must produce
the same bits. Conflating the two would let a genuine nondeterminism hide inside the
tolerance band, so ``canonical`` renders every amount with ``float.hex()`` and
``TestTheDigestIsStricterThanTheTolerance`` asserts the gap explicitly: two projections the
tolerance calls equal have different digests.

**Three distinct claims, easy to confuse.**

1. *Determinism* -- two runs on identical inputs agree. Asserted as a property over
   generated purchases, not on one example, because a single scenario cannot show that the
   agreement is a property of the engine rather than of that scenario.
2. *Sensitivity* -- two runs on inputs that differ at all disagree. A digest that always
   agreed would satisfy claim 1 perfectly and be worthless, which is the failure mode this
   suite would otherwise not see.
3. *Independence from provenance* -- filling in a ``verified_on`` does not move the digest.
   ``tests/unit/test_results_canonical.py`` already asserts this of the canonical *form*;
   what is asserted here is the same claim one level up, of the **digest and the manifest**,
   because that is the artifact C4 actually compares. If verifying a source moved the
   digest, C4 would fail on a documentation edit and the only available fix would be to stop
   trusting C4. The manifest still *records* the verification state, so the fact is not lost
   -- it is simply not part of the identity of the arithmetic.

**Why a subprocess appears in a determinism suite.** Python's string and frozenset hashing
is randomised per process (``PYTHONHASHSEED``). A digest that reached a ``frozenset``'s
iteration order would therefore be stable within one process -- green all day locally and in
CI -- and differ between two runs on the same machine. Comparing digests computed under two
different hash seeds is the only way to see that from inside a test.

Tracked as **C4** in ``docs/REQUIRED_TESTS.md``. Closes FR-012 and SC-006.
"""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from terezy.core.instruments import registry as instrument_registry
from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.ledger import canonical as ledger_canonical
from terezy.core.ledger.events import Event
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.provenance import SourceRef
from terezy.core.primitives.tolerance import TOLERANCE, is_close
from terezy.core.results import canonical, project
from terezy.core.results.project import Projection
from terezy.data import manifest
from terezy.data.declarations import resolver
from tests import synthetic

pytestmark = pytest.mark.invariant

UAH = Currency.UAH

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
ISSUE_A = "ovdp_synthetic_a"

FACE_VALUE = 1000.0
"""The synthetic issue's face value per unit, for sizing generated purchases at par."""


def _projection(
    *,
    quantity: float,
    cost: float,
    purchased_on: date,
    verified: bool = False,
    consumption_method: str = "fifo",
) -> Projection:
    """One projection of the hand-built synthetic issue, from stated inputs.

    ``verified`` toggles only the terms source's verification date, which is precisely the
    change that must leave the digest untouched.
    """
    source = replace(
        synthetic.TERMS_SOURCE,
        verified_on=date(2026, 8, 21) if verified else None,
    )
    provenance = prov.of([source])
    terms = synthetic.terms(
        face_value=Money(FACE_VALUE, UAH, provenance),
        provenance=provenance,
    )
    outcome = project.project(
        synthetic.declaration(terms=terms),
        synthetic.holding(
            quantity=quantity,
            purchased_on=purchased_on,
            cost=Money(cost, UAH, prov.of([synthetic.PURCHASE_SOURCE])),
        ),
        DateRange(start=purchased_on, end=date(2028, 1, 31)),
        synthetic.assumptions(consumption_method=consumption_method),
        tax_classes=synthetic.TAX_PACK,
    )
    assert isinstance(outcome, Projection), f"expected a projection, got {outcome!r}"
    return outcome


def _digest(result: Projection) -> str:
    return manifest.digest(canonical.of_projection(result))


def _digest_of_stream(items: Sequence[Event]) -> str:
    """The digest of a bare event stream, composed here rather than in the manifest.

    ``core.ledger.canonical`` says what identifies one *event*; what identifies a whole
    *result* is ``of_result`` and ``of_projection``. A loose stream is neither, so the
    composition is a fact about this test rather than a form the manifest needs to know.
    """
    return manifest.digest(tuple(ledger_canonical.of_event(event) for event in items))


PURCHASES = st.builds(
    lambda quantity, price_factor, purchased_on: (
        float(quantity),
        round(quantity * FACE_VALUE * price_factor, 2),
        purchased_on,
    ),
    quantity=st.integers(min_value=2, max_value=500),
    price_factor=st.floats(min_value=0.85, max_value=1.15, allow_nan=False, allow_infinity=False),
    purchased_on=st.dates(min_value=date(2026, 1, 15), max_value=date(2027, 12, 1)),
)
"""Whole-unit purchases at a plausible price, on any date in the issue's life.

Whole units and a bounded price factor keep every draw a *feasible* purchase -- above the
declared minimum ticket, before maturity -- so the property under test is determinism
rather than the failure path, which has its own tests. A generated infeasible purchase
would make this suite assert that two refusals are equal, which is true and uninteresting.
"""

QUIET = settings(
    max_examples=25,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
"""Fewer examples than a Hypothesis default, because each one folds a whole ledger twice.

``deadline=None`` because the first example pays for the module import and would otherwise
flake on a cold machine -- a timing flake in a determinism suite is worse than useless, since
it teaches a reader to rerun a red C4.
"""


class TestTwoRunsOnIdenticalInputsAgree:
    """Claim 1: determinism, as a property over generated purchases."""

    @given(PURCHASES)
    @QUIET
    def test_the_digest_of_a_projection_is_a_function_of_its_inputs(
        self, purchase: tuple[float, float, date]
    ) -> None:
        quantity, cost, purchased_on = purchase
        first = _projection(quantity=quantity, cost=cost, purchased_on=purchased_on)
        second = _projection(quantity=quantity, cost=cost, purchased_on=purchased_on)
        assert _digest(first) == _digest(second)

    @given(PURCHASES)
    @QUIET
    def test_the_instruments_own_event_stream_is_deterministic(
        self, purchase: tuple[float, float, date]
    ) -> None:
        """The contract's obligation on ``EventsFn``: called twice, equal results.

        Checked against the digest rather than by record equality, because equality of a
        ``Money`` deliberately ignores provenance -- two streams could compare equal while
        rendering differently, and it is the rendering the manifest records.
        """
        quantity, cost, purchased_on = purchase
        ops = instrument_registry.ops_for(instrument_registry.FIXED_INCOME)
        declaration = synthetic.declaration()
        holding = Holding(
            owner_id="owner-1",
            instrument_id=declaration.id,
            quantity=quantity,
            purchased_on=purchased_on,
            cost=Money(cost, UAH, prov.of([synthetic.PURCHASE_SOURCE])),
        )
        horizon = DateRange(start=purchased_on, end=date(2028, 1, 31))
        assumptions = synthetic.assumptions()
        first = ops.events(declaration, holding, horizon, assumptions)
        second = ops.events(declaration, holding, horizon, assumptions)
        assert isinstance(first, tuple)
        assert isinstance(second, tuple)
        assert _digest_of_stream(first) == _digest_of_stream(second)

    def test_the_loaded_declaration_path_is_deterministic_too(self) -> None:
        """Reading the files twice must produce the same result, not merely a similar one.

        The loader builds source ids from file and table names, so this also asserts that
        nothing in it depends on directory iteration order.
        """
        digests = set()
        for _ in range(2):
            declarations = resolver.from_data_root(DATA_ROOT)
            declaration = declarations.instruments[ISSUE_A]
            outcome = project.project(
                declaration,
                Holding(
                    owner_id="owner-1",
                    instrument_id=ISSUE_A,
                    quantity=10.0,
                    purchased_on=declaration.terms.issue_date,
                    cost=Money(10_000.0, UAH, prov.EMPTY),
                ),
                DateRange(start=declaration.terms.issue_date, end=date(2028, 1, 31)),
                synthetic.assumptions(),
                tax_classes=declarations.tax_classes,
            )
            assert isinstance(outcome, Projection)
            digests.add(_digest(outcome))
        assert len(digests) == 1

    def test_the_digest_survives_a_different_hash_seed(self) -> None:
        """The same scenario in two processes with different string hashing agrees.

        This is the only assertion in the suite that can see a digest reading a
        ``frozenset``'s iteration order or a ``dict``'s -- a real nondeterminism that is
        invisible within one process and would make two runs on the same machine disagree.
        """
        digests = {_run_in_subprocess(seed) for seed in ("0", "1")}
        assert len(digests) == 1, f"the digest depends on PYTHONHASHSEED: {digests}"
        assert digests == {_digest(_projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE))}


ISSUE = date(2026, 1, 15)
"""The synthetic issue's issue date -- the purchase date of the reference scenario."""

_SUBPROCESS_SCRIPT = """
import sys
from datetime import date

sys.path.insert(0, {root!r})

from terezy.core.instruments.interface import DateRange, Holding
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.results import canonical, project
from terezy.data import manifest
from tests import synthetic

outcome = project.project(
    synthetic.declaration(),
    synthetic.holding(),
    synthetic.horizon(),
    synthetic.assumptions(),
    tax_classes=synthetic.TAX_PACK,
)
print(manifest.digest(canonical.of_projection(outcome)))
"""
"""The reference scenario, computed in a fresh interpreter. Kept to the fixture defaults --
ten units at par on the issue date -- so the parent can reproduce it in one line."""


def _run_in_subprocess(hash_seed: str) -> str:
    """The reference scenario's digest, computed under a stated ``PYTHONHASHSEED``."""
    completed = subprocess.run(
        [sys.executable, "-c", _SUBPROCESS_SCRIPT.format(root=str(REPO_ROOT))],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "PYTHONHASHSEED": hash_seed},
    )
    assert completed.returncode == 0, completed.stderr
    return completed.stdout.strip()


class TestADifferentInputProducesADifferentDigest:
    """Claim 2: sensitivity. A digest that always agreed would pass claim 1 and be useless."""

    def test_a_different_quantity_changes_the_digest(self) -> None:
        assert _digest(_projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE)) != _digest(
            _projection(quantity=11.0, cost=11_000.0, purchased_on=ISSUE)
        )

    def test_a_different_purchase_date_changes_the_digest(self) -> None:
        assert _digest(_projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE)) != _digest(
            _projection(quantity=10.0, cost=10_000.0, purchased_on=date(2026, 3, 2))
        )

    def test_a_different_consumption_method_changes_the_digest(self) -> None:
        """FIFO and LIFO are different results even where they agree numerically.

        With one lot they consume the same basis, so every amount in the projection is
        identical -- and the *configuration* is part of what the result is a result of, so a
        digest that could not tell them apart would let a configuration change pass as a
        no-op.
        """
        assert _digest(
            _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, consumption_method="fifo")
        ) != _digest(
            _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, consumption_method="lifo")
        )

    @given(
        st.integers(min_value=2, max_value=100),
        st.integers(min_value=2, max_value=100),
    )
    @QUIET
    def test_distinct_quantities_never_share_a_digest(self, left: int, right: int) -> None:
        digests = {
            _digest(_projection(quantity=float(q), cost=q * FACE_VALUE, purchased_on=ISSUE))
            for q in (left, right)
        }
        assert len(digests) == (1 if left == right else 2)


class TestTheDigestIsStricterThanTheTolerance:
    """The gap research.md D5 asks for, asserted rather than described."""

    def test_two_projections_the_tolerance_calls_equal_have_different_digests(self) -> None:
        """A cost difference far inside the tolerance still moves the digest.

        ``1e-9`` of a hryvnia on ten thousand is a hundred-billionth of a percent -- money
        nobody would notice, and exactly the size of difference the tolerance exists to
        forgive when comparing against hand arithmetic. Determinism forgives nothing: the
        two runs are not the same run, so their digests must differ.
        """
        plain = _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE)
        nudged = _projection(quantity=10.0, cost=10_000.0 + TOLERANCE, purchased_on=ISSUE)
        assert is_close(
            plain.ledger.applied[0].amount.amount,
            nudged.ledger.applied[0].amount.amount,
        )
        assert _digest(plain) != _digest(nudged)

    def test_amounts_are_rendered_exactly_rather_than_rounded(self) -> None:
        """The mechanism behind the claim above: ``float.hex()``, not a decimal rendering."""
        result = _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE)
        rendered = canonical.of_projection(result)
        assert float.hex(10_000.0) in repr(rendered)
        assert "10000.0" not in repr(rendered)


def _terms_source(result: Projection) -> SourceRef:
    """The one source the two variants of a projection disagree about."""
    (source,) = [
        ref for ref in result.hurdle.provenance.sources if ref.id == synthetic.TERMS_SOURCE.id
    ]
    return source


class TestVerifyingASourceDoesNotMoveTheDigest:
    """Claim 3, at the level C4 actually compares: the digest and the manifest."""

    def test_the_digest_is_unchanged_by_filling_in_a_verification_date(self) -> None:
        assert _digest(
            _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, verified=False)
        ) == _digest(_projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, verified=True))

    def test_but_the_two_runs_really_do_differ_so_the_test_above_is_not_vacuous(self) -> None:
        """Guard against passing because both projections were identical anyway.

        The two runs genuinely disagree about the terms source: verified in one, not in the
        other. Both results stay *marked overall* either way, because the purchase and the
        exemption are unverified in both -- one unverified input taints the figure, which is
        the intended asymmetry -- so the check is on the ref itself rather than on the mark.
        """
        unverified = _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, verified=False)
        verified = _projection(quantity=10.0, cost=10_000.0, purchased_on=ISSUE, verified=True)
        assert _terms_source(unverified).verified_on is None
        assert _terms_source(verified).verified_on is not None
        assert prov.is_unverified(unverified.hurdle.provenance)

    def test_the_manifest_still_records_which_sources_were_unverified(self) -> None:
        """Excluded from the digest is not excluded from the record.

        The digest answers "is this the same arithmetic?"; the manifest answers "what did it
        rest on?". Losing the second to buy the first would be trading FR-015 for C4, and
        both are required.
        """
        declarations = resolver.from_data_root(DATA_ROOT)
        declaration = declarations.instruments[ISSUE_A]
        holding = Holding(
            owner_id="owner-1",
            instrument_id=ISSUE_A,
            quantity=10.0,
            purchased_on=declaration.terms.issue_date,
            cost=Money(10_000.0, UAH, prov.EMPTY),
        )
        horizon = DateRange(start=declaration.terms.issue_date, end=date(2028, 1, 31))
        assumptions = synthetic.assumptions()
        outcome = project.project(
            declaration, holding, horizon, assumptions, tax_classes=declarations.tax_classes
        )
        assert isinstance(outcome, Projection)
        record = manifest.of_run(
            result=outcome,
            declarations=declarations,
            holding=holding,
            horizon=horizon,
            assumptions=assumptions,
            seed=None,
        )
        assert record.result_digest == _digest(outcome)
        assert record.unverified_sources
        assert all(isinstance(name, str) for name in record.unverified_sources)


class TestTheEncodingCannotConfuseTwoDifferentResults:
    """The digest is only as sound as the bytes it is taken over."""

    @pytest.mark.parametrize(
        ("left", "right"),
        [
            (("a", "b"), ("ab",)),
            (("a",), (("a",),)),
            ((), ((),)),
            (("1",), (1,)),
            ((None,), ("",)),
            ((1, 2), (12,)),
            ((("a", "b"), ("c",)), (("a",), ("b", "c"))),
        ],
    )
    def test_distinguishable_structures_encode_distinguishably(
        self, left: tuple[object, ...], right: tuple[object, ...]
    ) -> None:
        """Length-prefixed strings and counted tuples, so concatenation cannot collide.

        Each pair here is a way a naive encoding fails: joining strings, flattening a
        nesting level, confusing an empty tuple with a tuple containing one, confusing a
        number with its own digits, or confusing an absent value with an empty string. All of
        them are differences a result could genuinely have.
        """
        assert manifest.encode(left) != manifest.encode(right)  # type: ignore[arg-type]
        assert manifest.digest(left) != manifest.digest(right)  # type: ignore[arg-type]

    def test_the_encoding_names_its_own_version(self) -> None:
        """A digest is comparable only within one encoding, so the encoding says which.

        Without this, changing the encoding would silently invalidate every digest ever
        recorded, and a stored manifest from before the change would look like a run that
        produced different numbers.
        """
        assert manifest.ENCODING.encode("utf-8") in manifest.encode(("anything",))

    def test_a_boolean_is_refused_rather_than_encoded_as_a_number(self) -> None:
        """``True`` is an ``int`` in Python, and would otherwise encode as ``1``.

        The canonical form's type does not admit a boolean, so this cannot happen through
        the typed path -- and a silent collision between ``True`` and ``1`` is exactly the
        class of confusion a digest exists to rule out, so it is refused rather than
        trusted to the type checker alone.
        """
        with pytest.raises(TypeError, match="boolean"):
            manifest.encode((True,))
