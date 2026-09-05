"""Two sources, kept apart, and the mark that rests on exactly one of them.

016 SC-010, SC-012, SC-013, SC-015, SC-016 and SC-021. The single worst outcome available in
this feature is a citation naming the issuer's depository beside a figure the issuer never
made: the register's authority would launder a seller's morning quotation, and a reader
walking the provenance would find a verifiable source behind an unverifiable number.
"""

from __future__ import annotations

import dataclasses
import tomllib
from collections.abc import Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Final, get_args

import pytest

from terezy.core.decision.answer import section_evaluated
from terezy.core.instruments.interface import EnumeratedTerms
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.primitives.tolerance import TOLERANCE
from terezy.core.results.tuple import BuysNoWholeUnit, TupleOutcome, TupleRefused
from terezy.data.declarations import resolver
from tests import answer_registries as answers
from tests import data_roots
from tests import observations as obs

pytestmark = pytest.mark.contract

DATA_ROOT: Final = data_roots.with_fixtures()
INSTRUMENTS: Final = DATA_ROOT / "instruments"
ACCESS: Final = DATA_ROOT / "access" / "instruments.toml"

REGISTER_URL: Final = "bank.gov.ua/depo_securities"
SELLER_URL: Final = "inzhur.reit/_api/assets"
DEALING_URL: Final = "https://www.inzhur.reit/offer/ovdp"

DECLARED_ISSUES: Final = 24
"""What the two shipped observations intersect to. Pinned in exactly one place, because the
prose in this repository says "23 of the 24" and "all 24" in several, and a partition asserted
without its size would keep passing over a population that grew. It cannot drift quietly: both
observation files are pinned to their own retrieval dates in `tests/observations.py`, so a
re-fetch fails there first."""

REFUSAL_MEMBERS: Final = 17
"""SC-021: 016 declared 24 instruments and widened nothing. 015 left the resale price's home
open precisely so that settling it late could not add an eighteenth member behind a landed
count -- and it is declared on the access record, so `DeclarationMissing(part="access")`
carries it and this number does not move."""


def _citations(table: Any, path: str = "") -> Iterator[tuple[str, str]]:
    """Every `source` string in a TOML document, with the table path that carries it."""
    if isinstance(table, dict):
        if isinstance(table.get("source"), str):
            yield path, table["source"]
        for key, value in table.items():
            yield from _citations(value, f"{path}.{key}" if path else key)
    elif isinstance(table, list):
        for index, item in enumerate(table):
            yield from _citations(item, f"{path}[{index}]")


def _document(path: Path) -> Any:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _declared_files() -> list[Path]:
    return [INSTRUMENTS / f"{isin}.toml" for isin in obs.declared_isins()]


def test_no_source_note_anywhere_names_both_sources() -> None:
    """SC-010, FR-020. One source, one retrieval date, one thing supplied."""
    documents = [(path, _document(path)) for path in [*_declared_files(), ACCESS]]
    for path, document in documents:
        for table, source in _citations(document):
            names = {REGISTER_URL in source, SELLER_URL in source}
            assert names != {True}, f"{path.name}:{table} names both sources"


def test_every_term_cites_the_register_and_every_price_cites_the_seller() -> None:
    """The positive half. A missing citation would pass the test above by naming neither."""
    for path in _declared_files():
        document = _document(path)
        for table, source in _citations(document["instrument"], "instrument"):
            expected = DEALING_URL if table == "instrument.constraints" else REGISTER_URL
            assert expected in source, f"{path.name}:{table}"
    quoted = {
        entry["instrument_id"]: entry
        for entry in _document(ACCESS)["access"]
        if entry["instrument_id"] in set(obs.declared_isins())
    }
    assert set(quoted) == set(obs.declared_isins())
    for isin, entry in quoted.items():
        for table in ("price", "resale_price"):
            assert SELLER_URL in entry[table]["source"], f"{isin}.{table}"


def test_every_register_citation_carries_the_endpoint_url() -> None:
    """FR-013. Article 10-1 part 2 of Law 2939-VI conditions reuse of open data on a reference
    to the source, and the URL is that reference. The Ukrainian text is in each citation."""
    for path in _declared_files():
        for table, source in _citations(_document(path)["instrument"], "instrument"):
            if REGISTER_URL in source:
                assert f"https://{REGISTER_URL}" in source, f"{path.name}:{table}"


def test_no_citation_claims_a_hyperlink_is_a_statutory_obligation() -> None:
    """FR-013's second half. The hyperlink wording belongs to point 17 of the Cabinet's
    Regulation 835, which prescribes a notice the PUBLISHER displays on its own dataset page;
    the word does not occur in the Act at all, so no citation here may claim it is a duty."""
    for path in [*_declared_files(), ACCESS]:
        for table, source in _citations(_document(path)):
            assert "гіперпосилання" not in source, f"{path.name}:{table}"


def test_every_declared_minimum_cites_the_venues_dealing_terms_and_is_not_a_price() -> None:
    """SC-015. The venue is primary for its own conditions of dealing and for nothing else."""
    declared = resolver.tuple_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    for isin in obs.declared_isins():
        constraints = declared.instruments.instruments[isin].constraints
        assert constraints.min_unit == 1.0, isin
        cited = list(constraints.provenance.sources)
        assert len(cited) == 1, isin
        assert DEALING_URL in cited[0].citation, isin
        assert cited[0].retrieved_on == date(2026, 8, 31), isin
        quote = declared.access[isin].quote
        assert quote is not None
        assert abs(constraints.min_ticket.amount - quote.price.amount) > TOLERANCE, isin


def test_the_venues_approximate_floor_is_not_the_cost_of_a_unit_on_any_issue() -> None:
    """The consequence of «приблизно», measured rather than smoothed away.

    The venue's floor is in UNITS -- «від 1 цінного паперу» -- and its money figure is the
    venue's own approximation of one, so the declared `min_ticket` is **below** the cost of a
    unit on 23 of the 24 and above it on `UA4000207518`, quoted at 989.47.

    Neither direction leaves the understatement FR-018 puts in the highest severity class, and
    the reason is `min_unit` rather than luck: `BuysNoWholeUnit` reports an amount that will not
    buy one whole increment, with the shortfall, rather than rounding it up. `min_ticket` is the
    money term the form requires and the venue's own published figure is the only one this
    project may write for it.
    """
    declared = resolver.tuple_from_data_root(
        DATA_ROOT, base_currency=Currency.UAH, scenario_id=None
    )
    floor = {
        isin: declared.instruments.instruments[isin].constraints.min_ticket.amount
        for isin in obs.declared_isins()
    }
    assert len(floor) == DECLARED_ISSUES
    above = [isin for isin in floor if obs.seller_bonds()[isin]["buy"] < floor[isin]]
    assert above == ["UA4000207518"]
    assert floor[above[0]] - obs.seller_bonds()[above[0]]["buy"] == pytest.approx(10.53, abs=5e-3)
    below = [isin for isin in floor if obs.seller_bonds()[isin]["buy"] > floor[isin]]
    assert set(below) == set(floor) - {above[0]}
    assert BuysNoWholeUnit in get_args(TupleRefused), (
        "the unit floor is what enforces the venue's real minimum; if this refusal goes, the "
        "money term above is the only one left and it is below the price of a unit"
    )


def _outcomes() -> list[TupleOutcome]:
    """Every evaluated outcome for a declared ОВДП across the owner's own three horizons."""
    answer = answers.answered()
    real = set(obs.declared_isins())
    return [
        item
        for section in answer.sections
        for item in section_evaluated(section)
        if item.key.instrument_id in real
    ]


def test_every_figure_from_a_real_issue_carries_the_unverified_mark() -> None:
    """SC-016, on a full tuple outcome rather than on a projection. Taint is asymmetric: the
    terms are the issuer's and could be checked, the price is a seller's morning quotation and
    never can, and one unverified input marks the result."""
    outcomes = _outcomes()
    assert outcomes, "the shipped registry must actually evaluate a real issue"
    for outcome in outcomes:
        assert prov.is_unverified(outcome.provenance), outcome.key.instrument_id


def test_the_mark_would_still_rest_on_the_quotation_if_every_term_were_verified() -> None:
    """SC-016's second half, and the only non-vacuous form of it.

    Every `verified_on` in the repository is empty today, so "the quotation's source is among
    the unverified" is true of every source at once and says nothing. What the separation of
    the two sources actually buys is that the terms COULD be verified and the price never can
    -- so the claim is tested by verifying them: a scratch registry in which every citation
    naming the register carries a verification date still produces a marked figure, and the
    only ones the register supplied are gone. What still marks the figure is the seller's
    quotation -- plus the route fees and the tax rate, which are other features' to verify.
    """
    supplied = _with_verified_terms()
    outcomes = [
        item
        for section in answers.answered(supplied=supplied).sections
        for item in section_evaluated(section)
        if item.key.instrument_id in set(obs.declared_isins())
    ]
    assert outcomes, "the scratch registry must still evaluate a real issue"
    for outcome in outcomes:
        assert prov.is_unverified(outcome.provenance), outcome.key.instrument_id
        left = prov.unverified_sources(outcome.provenance)
        assert left, outcome.key.instrument_id
        assert not [ref for ref in left if REGISTER_URL in ref.citation], outcome.key
        assert [ref for ref in left if SELLER_URL in ref.citation], outcome.key


def _with_verified_terms() -> Any:
    """The declared registry with every register-sourced citation given a verification date.

    Built in memory rather than as a scratch data root, because `scripts/check_provenance.py`
    refuses a verification date on an enumerated schedule and the point here is what the
    ENGINE does with one, not what the gate permits (016 FR-011 records that collision).
    """
    checked = date(2026, 8, 31)

    def verify(item: prov.Provenance) -> prov.Provenance:
        return prov.of(
            dataclasses.replace(ref, verified_on=checked)
            if REGISTER_URL in ref.citation or DEALING_URL in ref.citation
            else ref
            for ref in item.sources
        )

    def verify_terms(terms: Any) -> Any:
        checked_terms = dataclasses.replace(terms, provenance=verify(terms.provenance))
        if not isinstance(terms, EnumeratedTerms):
            return checked_terms
        return dataclasses.replace(
            checked_terms,
            payments=tuple(
                dataclasses.replace(
                    payment,
                    amount=dataclasses.replace(
                        payment.amount, provenance=verify(payment.amount.provenance)
                    ),
                )
                for payment in terms.payments
            ),
        )

    supplied = answers.inputs()
    instruments = {
        name: dataclasses.replace(
            item,
            terms=verify_terms(item.terms),
            constraints=dataclasses.replace(
                item.constraints, provenance=verify(item.constraints.provenance)
            ),
        )
        for name, item in supplied.registries.instruments.items()
    }
    return dataclasses.replace(
        supplied,
        registries=dataclasses.replace(supplied.registries, instruments=instruments),
    )


def test_no_reported_figure_equals_the_buy_versus_sell_spread() -> None:
    """SC-012, by a walk over every result record for a declared issue.

    FR-015: the spread is the seller's round trip on an IMMEDIATE resale, an exit this engine
    does not model, and the round trip a comparison reports is Principle VI's -- the way in,
    the purchase, the schedule to its end, and the way out. The five issues quoting buy equal
    to sell are excluded, because a zero spread is indistinguishable from a zero cost and the
    assertion would be vacuous on them rather than true.
    """
    spreads = {
        isin: obs.seller_bonds()[isin]["buy"] - obs.seller_bonds()[isin]["sell"]
        for isin in obs.declared_isins()
    }
    checked = 0
    for outcome in _outcomes():
        spread = spreads[outcome.key.instrument_id]
        if spread <= TOLERANCE:
            continue
        checked += 1
        for amount in _money(outcome):
            assert abs(amount - spread) > TOLERANCE, (outcome.key.instrument_id, amount)
    assert checked, "every declared issue quotes buy equal to sell; the walk saw nothing"


def _money(record: object, seen: set[int] | None = None) -> Iterator[float]:
    """Every money amount reachable from a result record, however deeply nested."""
    seen = set() if seen is None else seen
    if id(record) in seen:
        return
    seen.add(id(record))
    if isinstance(record, Money):
        yield record.amount
        return
    if dataclasses.is_dataclass(record) and not isinstance(record, type):
        for field in dataclasses.fields(record):
            yield from _money(getattr(record, field.name), seen)
        return
    if isinstance(record, (list, tuple, set, frozenset)):
        for item in record:
            yield from _money(item, seen)
    elif isinstance(record, dict):
        for item in record.values():
            yield from _money(item, seen)


def test_a_quotation_past_its_threshold_is_stale_and_still_produces_figures() -> None:
    """SC-013, FR-016. Staleness and verification are separate marks and neither refuses a run:
    a stale price is a price somebody should re-fetch, not an absent one."""
    threshold = timedelta(days=365)
    late = obs.SELLER_RETRIEVED_ON + threshold + timedelta(days=1)
    answer = answers.answered(as_of=late)
    real = set(obs.declared_isins())
    evaluated = [
        item
        for section in answer.sections
        for item in section_evaluated(section)
        if item.key.instrument_id in real
    ]
    assert evaluated, "a stale quotation must still produce figures"
    for outcome in evaluated:
        stale = {entry.source_id for entry in outcome.staleness.stale}
        assert stale, outcome.key.instrument_id
        assert any("access/instruments.toml" in name for name in stale), (
            outcome.key.instrument_id,
            sorted(stale),
        )


def test_declaring_twenty_four_instruments_widened_no_union() -> None:
    """SC-021, and the count 015 deliberately left for 016 not to move."""
    assert len(get_args(TupleRefused)) == REFUSAL_MEMBERS


def test_no_declaration_carries_a_field_the_record_did_not_already_have() -> None:
    """SC-021's other half: no new field on the instrument declaration record, so every key in
    a real issue's file is one a fixture could already have written."""
    fixture_keys: set[str] = set()
    real_keys: set[str] = set()
    declared = resolver.from_data_root(DATA_ROOT)
    for path in sorted(INSTRUMENTS.glob("*.toml")):
        document = _document(path)["instrument"]
        name = document["id"]
        target = real_keys if name in set(obs.declared_isins()) else fixture_keys
        target.update(_keys(document))
        if name in set(obs.declared_isins()):
            assert isinstance(declared.instruments[name].terms, EnumeratedTerms)
    assert real_keys <= fixture_keys, real_keys - fixture_keys


def _keys(table: Any, path: str = "") -> Iterator[str]:
    if isinstance(table, dict):
        for key, value in table.items():
            yield f"{path}.{key}" if path else key
            yield from _keys(value, f"{path}.{key}" if path else key)
    elif isinstance(table, list):
        for item in table:
            yield from _keys(item, path)
