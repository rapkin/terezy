"""FR-025 and FR-028: staleness is per kind of value, and measured against an as-of date.

Two requirements meet here, and each rules out the shortcut the other would tempt.

**FR-028 -- the threshold is per kind of value, declared with the kind.** A peer-to-peer
premium ages in days; a bank's published fee schedule ages in years; a regulatory limit
changes when the regulator says so. One project-wide threshold would either cry wolf on fee
schedules or stay silent on premiums, and a staleness warning that is usually wrong is one
that gets ignored -- which is worse than none. So the interesting case is not "an old value
is stale" but **two values retrieved on the same day, of different kinds, disagreeing about
whether they are stale**. That is what a per-kind threshold buys, and it is the first test
below.

**FR-025 -- staleness surfaces on every figure derived from a stale input**, which means the
verdict has to be a value that merges, exactly as the unverified mark does. The merge tests
here are the reason a ``RampCost`` built from four legs and two channels can carry one
verdict without any site having to remember to combine them.

**No clock** (research.md D9). ``as_of`` is a parameter, so the same inputs produce the same
verdicts forever. A clock would make a run's output depend on the day it was run, breaking
C4 determinism for a convenience -- and it would make a projection into the future report
every one of its inputs as stale, which is the specific absurdity that keeps ``as_of`` and
``on_date`` separate arguments. The last test in this module is a textual scan, because no
other gate can see a clock: ``datetime`` cannot be added to ``.importlinter``'s forbidden
list (the whole engine is dated), so "no clock in the core" is only checkable by reading.

**No permissive default anywhere.** A kind with no threshold cannot be constructed, and a
table naming an undeclared kind raises rather than resolving to something lenient. Both are
asserted below, because a staleness check that silently passes is worse than none at all --
it is a green tick over an unchecked value.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind, StalenessVerdict

pytestmark = pytest.mark.contract

RETRIEVED = date(2026, 1, 1)

P2P_PREMIUM = ObservationKind(
    id="p2p_premium",
    staleness_days=7,
    note="A peer-to-peer premium moves with demand and can shift within a week.",
)
FEE_SCHEDULE = ObservationKind(
    id="bank_fee_schedule",
    staleness_days=365,
    note="A published tariff changes on the bank's own schedule, rarely mid-year.",
)
KINDS = {P2P_PREMIUM.id: P2P_PREMIUM, FEE_SCHEDULE.id: FEE_SCHEDULE}


def _source(name: str) -> SourceRef:
    """One unverified observation, retrieved on the shared date.

    ``verified_on=None`` throughout: every route number in this feature is unobserved at
    first run (spec.md, Assumptions), and staleness is a separate question from
    verification. A value can be verified and stale, or unverified and fresh.
    """
    return SourceRef(
        id=name,
        citation="SYNTHETIC FIXTURE -- invented observation, for a test of staleness only.",
        retrieved_on=RETRIEVED,
        verified_on=None,
    )


def _provenance(name: str) -> Provenance:
    return prov.of([_source(name)])


def _unverified_source(*, verified_on: date | None = None) -> SourceRef:
    """A source retrieved on RETRIEVED, unverified unless a verification date is given."""
    return SourceRef(
        id="fixture",
        citation="SYNTHETIC FIXTURE",
        retrieved_on=RETRIEVED,
        verified_on=verified_on,
    )


class TestTheThresholdIsPerKind:
    """FR-028, SC-015: same retrieval date, different kinds, different verdicts."""

    def test_two_kinds_with_one_retrieval_date_go_stale_at_different_ages(self) -> None:
        # 30 days after retrieval: the premium is long past its 7-day threshold, the fee
        # schedule is nowhere near its 365-day one. One threshold could not say both.
        as_of = date(2026, 1, 31)
        assert staleness.is_stale(_unverified_source(), P2P_PREMIUM, as_of=as_of)
        assert not staleness.is_stale(_unverified_source(), FEE_SCHEDULE, as_of=as_of)

    def test_the_longer_threshold_does_go_stale_eventually(self) -> None:
        # The complement of the test above: the fee schedule is not exempt, only slower.
        # Asserted so that a threshold accidentally read as "never" would fail here.
        as_of = date(2027, 6, 1)
        assert staleness.is_stale(_unverified_source(), FEE_SCHEDULE, as_of=as_of)

    def test_the_boundary_is_strictly_past_the_threshold(self) -> None:
        # 7 days after retrieval a 7-day threshold has been *reached*, not exceeded:
        # ``as_of - retrieved_on > staleness_days`` (research.md D9). Asserted on both
        # sides of the boundary, because an off-by-one here is invisible in normal use
        # and would silently shift every warning by a day.
        assert not staleness.is_stale(_unverified_source(), P2P_PREMIUM, as_of=date(2026, 1, 8))
        assert staleness.is_stale(_unverified_source(), P2P_PREMIUM, as_of=date(2026, 1, 9))


class TestAKindWithoutAThresholdCannotExist:
    """FR-028: no permissive default, in either direction."""

    def test_a_kind_cannot_be_built_without_a_staleness_threshold(self) -> None:
        # The record has no default, so the omission is a construction failure rather
        # than a lenient value. mypy rejects it too; this asserts the runtime half.
        with pytest.raises(TypeError):
            ObservationKind(id="p2p_premium", note="no threshold stated")  # type: ignore[call-arg]

    def test_a_table_naming_an_undeclared_kind_fails_naming_what_is_known(self) -> None:
        # The other direction: the kind registry is closed, exactly as the day-count
        # registry is. An unrecognised name must not resolve to anything.
        with pytest.raises(KeyError, match="unknown observation kind") as raised:
            staleness.kind_for(KINDS, "regulatory_limit")
        assert "p2p_premium" in str(raised.value)
        assert "bank_fee_schedule" in str(raised.value)

    def test_staleness_of_refuses_an_undeclared_kind_rather_than_reporting_fresh(self) -> None:
        # The failure mode worth naming: an unresolvable kind returning an empty verdict
        # would read as "nothing is stale" on a value nobody has aged.
        with pytest.raises(KeyError, match="unknown observation kind"):
            staleness.staleness_of(
                _provenance("routes/p2p.toml#leg0"),
                KINDS,
                kind="regulatory_limit",
                as_of=date(2026, 1, 31),
            )


class TestTheVerdictNamesWhyAndByHowMuch:
    """FR-017: a degraded outcome carries its reason, in structured form."""

    def test_a_stale_source_is_named_with_its_age_and_its_overdue_days(self) -> None:
        verdict = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 1, 31),
        )
        assert staleness.any_stale(verdict)
        (stale,) = verdict.stale
        assert stale.source_id == "channels/uah_usd.toml#p2p"
        assert stale.kind_id == "p2p_premium"
        assert stale.retrieved_on == RETRIEVED
        assert stale.age_days == 30  # 2026-01-31 minus 2026-01-01
        assert stale.threshold_days == 7
        assert stale.overdue_days == 23  # 30 - 7, stated so nobody has to subtract

    def test_a_fresh_source_is_assessed_and_not_listed_as_stale(self) -> None:
        verdict = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 1, 3),
        )
        assert not staleness.any_stale(verdict)
        assert verdict.assessed == ("channels/uah_usd.toml#p2p",)

    def test_an_unassessed_verdict_is_distinguishable_from_nothing_being_stale(self) -> None:
        # The hole this closes: a figure whose staleness was never evaluated would
        # otherwise carry the same empty verdict as one that was evaluated and found
        # fresh -- a silent permissive default wearing a green tick. ``assessed`` names
        # what was looked at, so "nobody checked" and "checked, all fresh" differ.
        assert staleness.UNASSESSED.assessed == ()
        assert not staleness.any_stale(staleness.UNASSESSED)
        fresh = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 1, 3),
        )
        assert fresh != staleness.UNASSESSED

    def test_provenance_resting_on_no_source_assesses_nothing(self) -> None:
        # A zero, a count, a starting balance: ``provenance.EMPTY`` is not an
        # observation, so there is nothing to age and nothing to claim.
        assert (
            staleness.staleness_of(prov.EMPTY, KINDS, kind="p2p_premium", as_of=RETRIEVED)
            == staleness.UNASSESSED
        )

    def test_a_value_retrieved_after_the_question_was_asked_is_not_reported_stale(self) -> None:
        # A backdated as-of date against a later retrieval gives a negative age. It is
        # reported as it is rather than clamped, and it is not stale: an observation
        # cannot have aged past a threshold before it existed. Nothing here invents a
        # verdict for it, because nothing here knows what today is.
        verdict = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2025, 12, 1),
        )
        assert not staleness.any_stale(verdict)


class TestVerdictsMergeAcrossSources:
    """FR-025: the mark reaches every figure, so verdicts have to combine like provenance.

    A ``RampCost`` rests on several legs and several channels, each with its own kind and
    its own retrieval date. Merging is what lets the figure carry one verdict without any
    call site remembering to combine them -- the same argument, and the same monoid shape,
    as ``provenance.merge``.
    """

    def _premium(self) -> StalenessVerdict:
        return staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 1, 31),
        )

    def _schedule(self) -> StalenessVerdict:
        return staleness.staleness_of(
            _provenance("routes/monobank.toml#leg1"),
            KINDS,
            kind="bank_fee_schedule",
            as_of=date(2026, 1, 31),
        )

    def test_one_stale_input_among_fresh_ones_makes_the_figure_stale(self) -> None:
        # The same asymmetry ``provenance.is_unverified`` has, for the same reason: a
        # figure is only as trustworthy as its least-trustworthy input, and marking only
        # when *every* input is stale would let one stale premium hide in a crowd.
        merged = staleness.merge(self._premium(), self._schedule())
        assert staleness.any_stale(merged)
        assert [source.source_id for source in merged.stale] == ["channels/uah_usd.toml#p2p"]
        assert merged.assessed == ("channels/uah_usd.toml#p2p", "routes/monobank.toml#leg1")

    def test_unassessed_is_the_identity_of_the_merge(self) -> None:
        one = self._premium()
        assert staleness.merge(one, staleness.UNASSESSED) == one
        assert staleness.merge(staleness.UNASSESSED, one) == one

    def test_the_merge_is_commutative_and_associative(self) -> None:
        # Evaluation order can never change a verdict, which is what makes it safe to
        # propagate mechanically through a fold over legs.
        left, right = self._premium(), self._schedule()
        assert staleness.merge(left, right) == staleness.merge(right, left)
        third = staleness.staleness_of(
            _provenance("routes/binance.toml#leg0"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 3, 1),
        )
        assert staleness.merge(staleness.merge(left, right), third) == staleness.merge(
            left, staleness.merge(right, third)
        )

    def test_merge_all_folds_from_unassessed(self) -> None:
        assert staleness.merge_all([]) == staleness.UNASSESSED
        assert staleness.merge_all([self._premium(), self._schedule()]) == staleness.merge(
            self._premium(), self._schedule()
        )

    def test_the_same_source_seen_twice_is_reported_once_at_its_worst(self) -> None:
        # Provenance is a set, so a source can reach a figure by two paths. The verdict
        # keeps one entry per source and keeps the *strictest* reading of it, so a
        # lenient second look cannot dilute a stale first one.
        strict = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="p2p_premium",
            as_of=date(2026, 1, 31),
        )
        lenient = staleness.staleness_of(
            _provenance("channels/uah_usd.toml#p2p"),
            KINDS,
            kind="bank_fee_schedule",
            as_of=date(2026, 1, 31),
        )
        merged = staleness.merge(strict, lenient)
        assert merged.assessed == ("channels/uah_usd.toml#p2p",)
        assert [source.overdue_days for source in merged.stale] == [23]


class TestTheVerdictComesFromTheArgumentsAndNothingElse:
    """No clock. The as-of date is an input to the run and is recorded in the manifest."""

    def test_the_same_arguments_give_the_same_verdict(self) -> None:
        args = (_provenance("channels/uah_usd.toml#p2p"), KINDS)
        first = staleness.staleness_of(*args, kind="p2p_premium", as_of=date(2026, 1, 31))
        second = staleness.staleness_of(*args, kind="p2p_premium", as_of=date(2026, 1, 31))
        assert first == second

    def test_a_different_as_of_gives_a_different_verdict(self) -> None:
        # The whole point of the parameter: asking the question on a different date is a
        # different question, and the answer moves with it rather than with the machine.
        provenance = _provenance("channels/uah_usd.toml#p2p")
        fresh = staleness.staleness_of(provenance, KINDS, kind="p2p_premium", as_of=RETRIEVED)
        stale = staleness.staleness_of(
            provenance, KINDS, kind="p2p_premium", as_of=date(2026, 1, 31)
        )
        assert not staleness.any_stale(fresh)
        assert staleness.any_stale(stale)


CLOCK = re.compile(r"\.now\s*\(|\.today\s*\(|utcnow|time\.time\s*\(|monotonic\s*\(")
"""Every way the standard library tells you what day it is, near enough to catch a slip."""

CLOCK_FREE_SOURCES = (
    Path("core/primitives/staleness.py"),
    Path("core/routes"),
    Path("core/streams"),
    Path("core/results"),
)
"""Named as packages rather than as individual modules on purpose.

A list of files goes stale the moment a module is added beside them, and it goes stale
silently -- the scan keeps passing over the files it still knows about. A package is
covered as it grows.
"""

SOURCE_ROOT = Path(__file__).resolve().parents[2] / "src" / "terezy"


def _python_files(relative: Path) -> list[Path]:
    target = SOURCE_ROOT / relative
    assert target.exists(), f"{relative} does not exist, so the scan below covers nothing"
    return sorted(target.rglob("*.py")) if target.is_dir() else [target]


def test_nothing_that_decides_staleness_can_read_a_clock() -> None:
    """The gate ``.importlinter`` cannot provide, because the engine needs ``datetime``.

    ``pathlib`` and ``socket`` can be banned outright; ``datetime`` cannot, since every
    date in this system is data. So the prohibition is on the *functions* that ask what
    today is, and the only way to check it is to read the source. A clock here would make
    a run's output depend on the day it was run.
    """
    offenders = [
        f"{path.relative_to(SOURCE_ROOT)}:{number}: {line.strip()}"
        for relative in CLOCK_FREE_SOURCES
        for path in _python_files(relative)
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1)
        if CLOCK.search(line)
    ]
    assert not offenders, "a clock reached the core, which breaks C4 determinism:\n" + "\n".join(
        offenders
    )


def test_the_clock_scan_would_actually_catch_a_violation() -> None:
    """A scan that matches nothing passes forever and protects nothing."""
    assert CLOCK.search("    now = datetime.now(tz=UTC)")
    assert CLOCK.search("    today = date.today()")
    assert CLOCK.search("    stamp = time.time()")
    assert not CLOCK.search("def is_stale(retrieved_on: date, *, as_of: date) -> bool:")


@pytest.mark.contract
class TestVerificationRefreshesTheAge:
    """FR-025 says "verification **or** retrieval date"; this is which one, and why.

    A value retrieved long ago and verified recently is **not** stale. Verifying against a
    primary source is the strongest refresh of confidence there is, and a staleness warning
    that fired on the one value the owner had actually checked is a warning that gets
    ignored -- worse than none at all.

    The asymmetry is deliberate: an unverified value ages from retrieval, which is every
    value in this project today and the stricter of the two readings.
    """

    def test_an_unverified_value_ages_from_retrieval(self) -> None:
        stale_by_then = date(2026, 1, 9)  # RETRIEVED + 8 days, p2p threshold is 7
        assert staleness.is_stale(_unverified_source(), P2P_PREMIUM, as_of=stale_by_then)

    def test_a_verification_refreshes_it(self) -> None:
        """Same retrieval date, same as-of date, verified in between: no longer stale."""
        stale_by_then = date(2026, 1, 9)
        verified = _unverified_source(verified_on=date(2026, 1, 8))
        assert not staleness.is_stale(verified, P2P_PREMIUM, as_of=stale_by_then)

    def test_the_verdict_ages_from_the_same_date_as_the_predicate(self) -> None:
        """If the two disagreed, a value could be stale by one measure and current by the
        other -- and the mark on a figure would not match the boolean beside it."""
        as_of = date(2026, 1, 9)
        verified = _unverified_source(verified_on=date(2026, 1, 8))
        verdict = staleness.staleness_of(
            prov.of([verified]),
            {P2P_PREMIUM.id: P2P_PREMIUM},
            kind=P2P_PREMIUM.id,
            as_of=as_of,
        )
        assert not verdict.stale
        assert not staleness.is_stale(verified, P2P_PREMIUM, as_of=as_of)

    def test_freshest_date_prefers_verification(self) -> None:
        assert staleness.freshest_date(_unverified_source()) == RETRIEVED
        assert staleness.freshest_date(_unverified_source(verified_on=date(2026, 6, 1))) == date(
            2026, 6, 1
        )

    def test_a_re_retrieval_after_an_old_verification_ages_from_the_retrieval(self) -> None:
        """FR-025 promises the *later* of the two dates, in both orderings.

        A value verified in 2024 and re-fetched on 2026-08-01 is 21 days old on
        2026-08-22, not 964: the retrieval is the more recent look at the source, and
        reporting it stale would tell the owner to re-fetch the value he just fetched.
        """
        re_retrieved = SourceRef(
            id="fixture",
            citation="SYNTHETIC FIXTURE",
            retrieved_on=date(2026, 8, 1),
            verified_on=date(2024, 1, 1),
        )
        assert staleness.freshest_date(re_retrieved) == date(2026, 8, 1)
        assert not staleness.is_stale(re_retrieved, P2P_PREMIUM, as_of=date(2026, 8, 7))
        # And the other ordering: a verification after retrieval wins, as before.
        re_verified = SourceRef(
            id="fixture",
            citation="SYNTHETIC FIXTURE",
            retrieved_on=date(2024, 1, 1),
            verified_on=date(2026, 8, 1),
        )
        assert staleness.freshest_date(re_verified) == date(2026, 8, 1)
        assert not staleness.is_stale(re_verified, P2P_PREMIUM, as_of=date(2026, 8, 7))
