"""The hurdle rate: the number every other option in this project must beat.

``SIMULATOR_SPEC.md`` §3.1 makes the claim the whole product rests on -- a Ukrainian
government bond bought through Inzhur costs nothing to enter and is taxed at nothing, so
its yield is the bar. This record is that claim turned into a computed, traceable figure,
and the type's *name* is how FR-004's "label it as the hurdle rate" is satisfied: a caller
cannot hold one of these and think it is something else.

**Two return figures, never one** (FR-005). They answer different questions and neither
substitutes for the other:

* :attr:`HurdleRate.nominal_ytm` -- the **contractual** yield to maturity: the annual rate
  at which the bond's promised gross cash flows discount back to what was paid for them.
  A property of the terms and the price.
* :attr:`HurdleRate.nominal_cash_flow_return` -- the **cash-flow-weighted** (money-weighted)
  return actually earned: the same root-finding applied to the flows net of every tax
  charge recorded in the ledger. A property of what the owner keeps.

Under an exempt class the two series are identical and the two figures agree, which is a
fact worth asserting rather than a reason to collapse them into one field. The moment a
taxed instrument arrives they diverge, and code that had only ever seen them equal would
have picked whichever it happened to store.

**Both are nominal, and the real slot beside them holds two figures** (FR-022; 007 FR-006,
FR-009). Feature 001 reserved :attr:`HurdleRate.real` and left it holding a typed
"unavailable" carrying its reason, so that the feature which introduced CPI could fill it
without changing the shape of the result or anything that consumes it. Feature 007 is that
feature, and the promise held: ``real`` is still exactly **one** field, and what it holds is
now a :class:`RealTerms` carrying two independently typed outcomes.

**Two, because the horizon has two halves and only one of them has been observed.** 001's
FR-022 forbade a real figure computed from an assumed inflation rate, and a hurdle projects
into the future where only assumptions exist. The owner resolved the collision on 2026-08-22:
*both figures, separately labelled, never mixed into one number.*
:attr:`RealTerms.realized` is deflated by declared CPI observations,
:attr:`RealTerms.assumed` by a declared future-inflation assumption, and neither ever stands
in for the other. The prohibition was refined rather than repealed -- a real figure from an
*implicit or invented* rate is still forbidden; a *declared, dated, labelled* assumption
entered as scenario data is a different thing and is visible as an assumption on every figure
it touches.

**A nominal figure still cannot be assigned into the slot without a mypy error**, which is
the mechanism decision D4 chose over a naming convention, and it survived the slot changing
occupant: ``NominalRate`` and ``RealRate`` share no base class and no protocol.

**The figure states its own boundaries** (:attr:`HurdleRate.excludes`). Principle VI
forbids quoting an access cost per instrument, so rather than pretending this number is
comparison-ready the record says what it does not account for. For OVDP through Inzhur the
excluded route costs happen to be reported as zero, which makes this figure nearly
complete for this one instrument -- and would make it badly misleading if compared against
a crypto ramp whose costs are five to ten percent one way.

**Why a hand-rolled bisection and not ``scipy.optimize``.** A yield is a root and needs a
root find. ``scipy`` is a project dependency, and the plan states plainly that this feature
does not use it: the arithmetic is tens of values in plain Python, and pulling an array
library into the middle of the one figure the project exists to produce would put a
compiled reduction between the inputs and the determinism digest (C4) for no benefit. A
bisection over a monotone function is twenty lines, has no tuning parameters, cannot
diverge, and runs the same way on every platform -- and the last of those is a hard
requirement here, not a preference.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, assert_never

from terezy.core.inflation import series as cpi
from terezy.core.inflation.deflate import deflate
from terezy.core.inflation.series import CpiObservation, CpiSeries, InflationAssumption
from terezy.core.primitives import periods, staleness
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.money import Money
from terezy.core.primitives.periods import Window
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import NominalRate, RealRate, RealTermsUnavailable
from terezy.core.primitives.staleness import Ageing, StalenessVerdict

type CashFlow = tuple[float, float]
"""One dated amount, as ``(years from the purchase, signed amount)``.

Years rather than a date, and a bare ``float`` rather than ``Money``: by this point the
figure is a dimensionless rate. The provenance of every amount behind it is unioned into
:attr:`HurdleRate.provenance` by the caller, which is the level at which a reader asks
whether the figure rests on anything unverified. Duplicating the mark on each intermediate
would create a second place for it to disagree with itself.
"""

EXCLUDES: Final[frozenset[str]] = frozenset(
    {
        "funding route costs (in)",
        "exit route costs (out)",
        "inflation (the figure is nominal)",
        "public holidays (weekends are observed; no holiday calendar is modelled)",
    }
)
"""What a hurdle rate does not account for **whatever it was computed from**, in the
output's own words.

Each item is a whole later feature or a stated deferral. They are phrased for a reader
rather than as identifiers because they are meant to be shown: a figure that silently
omitted a five-to-ten-percent access cost is the predecessor project's headline defect
(``REWRITE_BRIEF.md`` §4.2), and this set is the standing reminder of it.

⚙ **A floor, not the whole statement** (013 FR-023). What a figure excludes can depend on
what it was derived from, so :func:`of_flows` takes the set and this is its default. The
declaration supplies anything it adds; nothing here knows what that might be.
"""

ACCOUNTS_FOR: Final[frozenset[str]] = frozenset(
    {
        "tax on every taxable event over the holding's life",
    }
)
"""What the figure *is* net of, in the output's own words.

The sibling of :data:`EXCLUDES`, and the reason it exists is US1's second acceptance
scenario: the figure must **state** that it is after tax. A return that does not say
whether it is gross or net is exactly the ambiguity Principle I exists to prevent -- and
between two instruments where one is taxed at 0% and another at 23%, that ambiguity is
the whole decision.

Naming what is included beside what is excluded also means a later feature cannot quietly
move a term from one set to the other: adding route costs means deleting a line here and
adding one there, in the same change, where a reviewer sees both.
"""

# ---------------------------------------------------------------------------
# 007-cpi-real-terms: the real slot, filled
# ---------------------------------------------------------------------------
#
# Feature 001 left one generic sentence here -- that the feature did not model inflation at
# all -- and it was true then. It stops being true the moment this feature lands, so it
# survives nowhere in `src/`, and a test greps for it. FR-012 replaces it with reasons that
# name the specific absence, built by the functions below so that every result says it the
# same way and no call site improvises.
#
# `real_terms` is the only place a `RealTerms` is built, and it checks coverage BEFORE any
# arithmetic runs. That ordering is the design (plan.md, Complexity Tracking): a check inside
# the computation is a check someone later moves, reorders or short-circuits.


@dataclass(frozen=True, slots=True, kw_only=True)
class RealTerms:
    """The real-terms slot: two figures, computed independently, never mixed.

    **Never itself unavailable.** When neither figure can be computed this record still
    exists and holds two unavailable values, each with its own reason -- because *"which of
    the two is missing"* is exactly what FR-012 requires answering, and a single unavailable
    value cannot answer it (research.md D2).

    **And it is what the one reserved field holds**, rather than being two fields on
    :class:`HurdleRate`. FR-009 wants two figures and FR-006 wants the result's shape
    unchanged; those are only compatible if the *slot* stays one field and the *occupant*
    carries both. A second field on ``HurdleRate`` would have broken the invariance that
    001's FR-022 existed to create, which would be an odd way to honour it.

    There is deliberately **no third field** combining the two. No reported number blends
    observed and assumed inflation (FR-010), and the way to keep that true is to have nowhere
    to put one.
    """

    realized: RealRate | RealTermsUnavailable
    """Deflated by declared CPI observations covering the whole window, or the reason not."""

    assumed: RealRate | RealTermsUnavailable
    """Deflated by the declared future-inflation assumption, or the reason not.

    Independent of :attr:`realized`: one being unavailable never makes the other unavailable,
    and one being available never stands in for the other.
    """


def no_series_declared() -> RealTermsUnavailable:
    """FR-012: this run was given no CPI series.

    The wording says *given* rather than *declared* on purpose. A series can be absent because
    nobody declared one or because a caller forgot to pass the one that exists, and from inside
    the core those are the same fact -- so the reason states what it can see rather than
    guessing at a cause and sending the reader to the wrong file.
    """
    return RealTermsUnavailable(
        reason=(
            "this run was given no CPI series, so there is nothing to deflate by. "
            "None is assumed: a real rate derived from an undeclared inflation rate would be "
            "a fabricated number wearing the same label as a measured one."
        )
    )


def no_nominal_figure() -> RealTermsUnavailable:
    """FR-012: there is a deflator but no figure to deflate.

    Distinct from :func:`no_series_declared`, and the distinction is the requirement: *"there
    is nothing to deflate"* and *"there is nothing to deflate by"* send a reader to two
    different files.
    """
    return RealTermsUnavailable(
        reason=(
            "there is no nominal figure to deflate, so no real counterpart of it exists. "
            "This is distinct from having no price data: the deflator may be complete and "
            "there is still nothing for it to act on."
        )
    )


def no_assumption_declared() -> RealTermsUnavailable:
    """FR-012 and FR-015: the projected portion has no declared inflation assumption.

    **No default rate, and none may be added.** The refusal is the feature, not a gap in it:
    a default would be an invented belief about the future wearing the owner's label.
    """
    return RealTermsUnavailable(
        reason=(
            "this run was given no future-inflation assumption, so the projected "
            "portion of the horizon has no inflation rate to deflate by. There is no default "
            "rate: one would be a belief about the future that the owner never stated, "
            "presented as though he had."
        )
    )


def window_not_covered(
    series_id: str, window: Window, missing: Sequence[str]
) -> RealTermsUnavailable:
    """FR-004 and FR-012: the declared series has a gap inside the window, named month by month."""
    return RealTermsUnavailable(
        reason=(
            f"the declared CPI series {series_id!r} does not cover every month of "
            f"{window.first}..{window.last}: {len(missing)} month(s) have no declared "
            f"observation ({', '.join(missing)}). Nothing is interpolated and nothing is "
            "carried forward, and the window is not shortened to the part that is covered -- "
            "a real rate over the covered months would be a correct answer to a question "
            "nobody asked. Declaring the missing observations is the fix."
        )
    )


def window_has_no_elapsed_month(window: Window) -> RealTermsUnavailable:
    """FR-012: the window spans no month, so there is no price change to deflate by.

    Refused rather than answered with "zero inflation", which would come back as a real rate
    exactly equal to the nominal one -- a confident wrong answer that looks entirely
    reasonable.
    """
    return RealTermsUnavailable(
        reason=(
            f"the deflation window {window.first}..{window.last} contains no elapsed month, "
            "so there is no measured price change to deflate by. It is reported rather than "
            "treated as zero inflation: that would return a real rate equal to the nominal "
            "one, which is a confident answer to a question that has no data behind it."
        )
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class Deflation:
    """What one run brings to the deflation: the span, and the two possible deflators.

    A record rather than three parameters on :func:`of_flows`, because the three are one
    statement -- *"deflate over this window, with whatever of these two is declared"* -- and a
    window without either deflator, or a deflator without a window, is half a statement. The
    caller assembles it once from the run's inputs.

    Both deflators are ``None``-able and neither has a default: their absence is a *reported
    reason* rather than an error (FR-012), and which one is absent decides which half of
    :class:`RealTerms` says so.
    """

    window: Window
    """The span the figures are deflated over, inclusive. See ``project._deflation_window``."""

    series: CpiSeries | None
    """The declared CPI series, or ``None`` when the run was given none."""

    assumption: InflationAssumption | None
    """The declared future-inflation assumption, or ``None`` when the run was given none."""

    ageing: Ageing | None
    """The declared staleness thresholds and the date the question is asked at, or ``None``.

    ``None`` means *this run did not ask* -- ageing needs an ``as_of`` and there is no clock to
    invent one from -- and the figures then carry
    :data:`~terezy.core.primitives.staleness.UNASSESSED`, which says nothing was checked rather
    than claiming everything is fresh. One optional record rather than two optional fields, so
    a caller cannot supply the thresholds, forget the date, and get silence (FR-005).
    """


NOT_DEFLATED: Final[RealTerms] = RealTerms(
    realized=no_series_declared(),
    assumed=no_assumption_declared(),
)
"""The real slot of a figure assembled without any deflation input.

Every reason in it is one of FR-012's named ones -- it says *no series was declared* and *no
assumption was declared*, which is exactly what happened. It is not a permissive default
hiding a skipped step: nothing was computed and the output says which two things were
missing.
"""


def real_terms(
    *,
    nominal: NominalRate | None,
    nominal_provenance: Provenance,
    nominal_staleness: StalenessVerdict,
    deflation: Deflation,
) -> RealTerms:
    """Both real figures for one nominal rate over one window. The only place a slot is filled.

    Pure: no clock, no I/O. Everything nullable inside :class:`Deflation` is nullable because
    its absence is a *reported reason* rather than an error -- the whole point of FR-012 -- and
    ``nominal`` is nullable for the same reason, so that "there is nothing to deflate" is a
    named answer instead of an unrepresentable state.

    ``nominal_provenance`` and ``nominal_staleness`` are separate from ``nominal`` because a
    :class:`~terezy.core.primitives.rates.NominalRate` carries neither: the union FR-013
    requires is over the *holding's* inputs and every observation used, and only the caller
    holds the first half.

    The window comes from :attr:`Deflation.window` and is **not** a second parameter. It was
    one briefly, and two places holding one span is two places that can disagree about what a
    figure covers -- with FR-011 requiring the figure to name it.

    **The two refusals that apply to both figures are decided here, once.** There is no figure
    to deflate, and the window spans no elapsed month: neither is a fact about a *deflator*, so
    neither belongs in a per-figure branch where one half could grow a guard the other lacks.
    That is not hypothetical -- it is the divergence a reviewer found in the first cut of this
    function, where ``_realized`` refused a reversed window by name while ``_assumed`` returned
    a rate whose ``window`` named a span containing no months, in breach of FR-011.

    Below that line the two figures are computed independently and neither is derived from the
    other. FR-010 forbids a single reported number blending observed and assumed inflation, and
    computing one from the other is how a blend gets in.
    """
    if nominal is None:
        return RealTerms(realized=no_nominal_figure(), assumed=no_nominal_figure())
    if not periods.months_in(deflation.window):
        return RealTerms(
            realized=window_has_no_elapsed_month(deflation.window),
            assumed=window_has_no_elapsed_month(deflation.window),
        )
    return RealTerms(
        realized=_realized(
            nominal=nominal,
            nominal_provenance=nominal_provenance,
            nominal_staleness=nominal_staleness,
            deflation=deflation,
        ),
        assumed=_assumed(
            nominal=nominal,
            nominal_provenance=nominal_provenance,
            nominal_staleness=nominal_staleness,
            deflation=deflation,
        ),
    )


def _realized(
    *,
    nominal: NominalRate,
    nominal_provenance: Provenance,
    nominal_staleness: StalenessVerdict,
    deflation: Deflation,
) -> RealRate | RealTermsUnavailable:
    """The figure deflated by declared observations, or the specific reason there is none.

    **Coverage is checked before any arithmetic.** The two guards that could equally apply to
    the assumed figure were hoisted into :func:`real_terms`, so this function refuses only what
    is genuinely its own: no series, and a series that does not cover the window.
    """
    series = deflation.series
    if series is None:
        return no_series_declared()

    covered = cpi.coverage(series, deflation.window)
    match covered:
        case cpi.NotCovered():
            return window_not_covered(series.id, deflation.window, covered.missing)
        case cpi.Covered():
            cumulative = cpi.cumulative_inflation(covered.observations)
            annual = cpi.annualised(
                cumulative,
                periods=len(covered.observations),
                per_year=cpi.periods_per_year(series.periodicity),
            )
            return RealRate(
                value=deflate(nominal=nominal.value, inflation=annual),
                basis="realized_cpi",
                series_id=series.id,
                window=deflation.window,
                provenance=prov.merge(nominal_provenance, cpi.provenance_of(covered.observations)),
                staleness=staleness.merge(
                    nominal_staleness,
                    _aged_observations(covered.observations, deflation.ageing),
                ),
            )
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(covered)


def _assumed(
    *,
    nominal: NominalRate,
    nominal_provenance: Provenance,
    nominal_staleness: StalenessVerdict,
    deflation: Deflation,
) -> RealRate | RealTermsUnavailable:
    """The figure deflated by the declared assumption, or the specific reason there is none.

    No coverage question arises: an assumption is a single rate per annum covering whatever
    span it is applied to, which is precisely what makes it an assumption rather than an
    observation. What the figure carries instead is ``basis="declared_assumption"`` on its
    face, everywhere it appears.

    A cited external forecast contributes its citation to the provenance, ages under its own
    declared kind, and is **still** labelled an assumption (FR-010). The citation says where
    the belief was read; it does not make next year's prices observed.
    """
    assumption = deflation.assumption
    if assumption is None:
        return no_assumption_declared()
    return RealRate(
        value=deflate(nominal=nominal.value, inflation=assumption.annual_rate),
        basis="declared_assumption",
        series_id=assumption.id,
        window=deflation.window,
        provenance=(
            nominal_provenance
            if assumption.provenance is None
            else prov.merge(nominal_provenance, assumption.provenance)
        ),
        staleness=staleness.merge(
            nominal_staleness, _aged_assumption(assumption, deflation.ageing)
        ),
    )


def _aged_observations(
    observations: Sequence[CpiObservation], ageing: Ageing | None
) -> StalenessVerdict:
    """The CPI side's verdict, or ``UNASSESSED`` when this run did not ask for one."""
    if ageing is None:
        return staleness.UNASSESSED
    return cpi.staleness_of_observations(observations, ageing.kinds, as_of=ageing.as_of)


def _aged_assumption(assumption: InflationAssumption, ageing: Ageing | None) -> StalenessVerdict:
    """The belief's verdict: ``UNASSESSED`` unless it is a retrieved forecast and a date was given.

    An owner's own belief returns ``UNASSESSED`` even when a date *was* given, and that is the
    honest answer rather than a shortcut: a belief has no retrieval date to age from, and it is
    superseded when the owner changes his mind rather than by a threshold expiring.
    """
    if ageing is None:
        return staleness.UNASSESSED
    return cpi.staleness_of_assumption(assumption, ageing.kinds, as_of=ageing.as_of)


_LOWEST_RATE: Final = -0.999999
"""The bottom of the bracket: a loss of all but a millionth of the investment.

Not ``-1.0``: at exactly ``-1`` the discount factor is a division by zero for any flow
after the purchase. A rate below this is not a rate this project will report -- it is a
total loss, and a total loss is described by saying so, not by quoting a percentage.
"""

_HIGHEST_RATE: Final = 100.0
"""The top of the bracket: 10 000% per annum. Above this the answer is not a yield."""

_MAX_ITERATIONS: Final = 200
"""Enough for the bracket to collapse to adjacent floats, with room to spare.

Halving a bracket of about 101 down to float resolution takes roughly sixty steps. The
cap exists so a bug cannot spin forever, not because the loop is expected to reach it.
"""


@dataclass(frozen=True, slots=True)
class HurdleRate:
    """The benchmark return of one holding, with its boundaries and its sources."""

    nominal_ytm: NominalRate
    """The contractual yield to maturity, in nominal terms. See the module docstring."""

    nominal_cash_flow_return: NominalRate
    """The cash-flow-weighted return net of tax, in nominal terms. Kept separate."""

    real: RealTerms
    """The real-terms figures: one deflated by observation, one by assumption, never mixed.

    ⚙ **Still exactly one field, and that is FR-006's whole content.** Feature 001 reserved
    this slot and left it holding a typed "unavailable"; feature 007 changed what occupies it
    and did not change the result's shape. Adding a second field beside this one would have
    broken the invariance the reservation existed to create.

    Never ``None`` and never a bare unavailable: :class:`RealTerms` always exists, and when
    neither figure can be computed it holds two reasons rather than one, because *which* half
    is missing is the question a reader is actually asking (FR-012).
    """

    total_tax: Money
    """Every tax charge over the life of the holding, summed. Exactly zero for an exempt
    class -- and zero because zeroes were recorded and added up, not because nothing
    was."""

    accounts_for: frozenset[str]
    """What this figure *is* net of -- in particular, that it is after tax (US1
    scenario 2). See :data:`ACCOUNTS_FOR`."""

    excludes: frozenset[str]
    """What this figure does not account for. See :data:`EXCLUDES`."""

    provenance: Provenance
    """The union of every source behind every amount that fed this figure.

    ``provenance.is_unverified`` is ``True`` while any of them lacks a verification date,
    which for the OVDP yield is the expected first-run state (FR-015, E5).
    """


def net_present_value(flows: Sequence[CashFlow], rate: float) -> float:
    """Discount a series of dated amounts back to the purchase date at ``rate``.

    **Annual compounding at a fractional exponent** -- ``(1 + r) ** years``, where
    ``years`` is a real number -- rather than per-period compounding on a count of whole
    periods. It is deliberately *not* continuous compounding: that would be
    ``exp(-r * years)`` and would give a different rate for the same flows. The year
    fractions come from the issue's declared day-count convention, so the annualisation
    is measured the same way the coupons were accrued; a separate hard-coded 365 here
    would make the yield disagree with the schedule it was computed from.
    """
    total = 0.0
    for years, amount in flows:
        total += amount / (1.0 + rate) ** years
    return total


def internal_rate_of_return(flows: Sequence[CashFlow]) -> float:
    """The rate at which ``flows`` discount to zero, found by bisection.

    Bisection rather than Newton: for a conventional series -- one payment out at the
    start, receipts afterwards -- the present value is strictly decreasing in the rate, so
    a bracket that straddles zero contains exactly one root and halving it cannot fail.
    Newton is faster and can leave the bracket on a badly conditioned series, which is a
    silent wrong answer rather than a slow one.

    Raises ``ValueError`` when the bracket does not straddle zero. That is a statement
    about the code, not about the money: by the time a series reaches here the purchase
    cost is known positive and the redemption known positive, which guarantees a sign
    change, so a failure means the caller built a series this function was never given.
    """
    low, high = _LOWEST_RATE, _HIGHEST_RATE
    at_low = net_present_value(flows, low)
    at_high = net_present_value(flows, high)
    if (at_low > 0.0) == (at_high > 0.0):
        raise ValueError(
            f"no yield exists between {low!r} and {high!r} for these cash flows: the "
            f"present value is {at_low!r} at the bottom of the bracket and {at_high!r} at "
            "the top, so it never crosses zero. A conventional purchase -- money out "
            "first, receipts afterwards -- always crosses; a series that does not is not "
            "one this function was given a definition for, and extrapolating past the "
            "bracket would invent a rate."
        )

    for _ in range(_MAX_ITERATIONS):
        middle = (low + high) / 2.0
        if middle in (low, high):
            # The bracket has collapsed to adjacent floats. Halving again would return
            # one of the endpoints unchanged and loop forever.
            break
        value = net_present_value(flows, middle)
        if value == 0.0:
            return middle
        if (value > 0.0) == (at_low > 0.0):
            low, at_low = middle, value
        else:
            # `high` moves without an accompanying `at_high`, and that is deliberate
            # rather than an oversight: the loop only ever compares a midpoint's sign
            # against `at_low`, so the upper endpoint's value is never read again after
            # the bracket check above. Tracking it would be a second variable that has to
            # stay correct and is never consulted.
            high = middle
    return (low + high) / 2.0


def of_flows(
    *,
    contractual: Sequence[CashFlow],
    received: Sequence[CashFlow],
    total_tax: Money,
    provenance: Provenance,
    excludes: frozenset[str] = EXCLUDES,
    nominal_staleness: StalenessVerdict = staleness.UNASSESSED,
    deflate_with: Deflation | None = None,
) -> HurdleRate:
    """Assemble the result from the two series, the tax total and the merged sources.

    Both series are required, and they are required *separately*, because computing one
    and reusing it for the other is the substitution FR-005 forbids. Under an exemption
    they happen to be identical -- and passing the same series twice would be a caller's
    honest statement that the flows really are the same, not this function's assumption
    that they always are.

    ⚙ **The figure that gets deflated is this function's own ``nominal_ytm``** (007 FR-007),
    which is why the deflation happens here rather than in the caller. The contractual yield
    is the benchmark the spec designates, and the real figure is *its* counterpart; computing
    the yield in one place and deflating a separately-derived copy of it in another would be
    two roots of the same equation with two chances to disagree. The caller supplies the
    window and the deflators; the rate comes from here.

    ⚙ **``nominal_staleness`` is what the caller knows about the ageing of the figure being
    deflated** (FR-013: a staleness report on *any input of the nominal figure* must reach the
    real figure). It defaults to :data:`~terezy.core.primitives.staleness.UNASSESSED` --
    *nobody aged anything* -- which is the honest verdict for a feature-001 hurdle rate and not
    a claim of freshness: 001's ``BondTerms``, ``InstrumentConstraints`` and ``TaxClass`` do not
    carry the observation kind they age under (see ``loader._source_ref``), so there is nothing
    here to age them against yet. The merge point exists so that the day those records carry
    their kind, one caller changes and every real figure inherits the verdict.

    ⚙ **``excludes`` defaults to :data:`EXCLUDES` and may be widened by the caller** (013
    FR-023). What a figure fails to account for is partly a property of what it was derived
    from, and the one case that exists is a purchase price that has not been separated into
    a clean price and accrued interest. The default is the floor rather than a permission:
    a caller may add to it and there is nothing here that takes anything away.

    ``deflate_with`` defaults to ``None``, and the default is **not** a permissive one: the
    slot then holds :data:`NOT_DEFLATED`, two of FR-012's named refusals saying that no series
    and no assumption were supplied -- which is exactly what happened. FR-006 and US1's fifth
    scenario require a call that ran under feature 001 to run here unchanged and produce a
    shape-identical result, and this is what makes that literally true.
    """
    nominal_ytm = NominalRate(internal_rate_of_return(contractual))
    return HurdleRate(
        nominal_ytm=nominal_ytm,
        nominal_cash_flow_return=NominalRate(internal_rate_of_return(received)),
        real=(
            NOT_DEFLATED
            if deflate_with is None
            else real_terms(
                nominal=nominal_ytm,
                nominal_provenance=provenance,
                nominal_staleness=nominal_staleness,
                deflation=deflate_with,
            )
        ),
        total_tax=total_tax,
        accounts_for=ACCOUNTS_FOR,
        excludes=excludes,
        provenance=provenance,
    )
