"""The four refusals a `cash_balance` declaration carries, each naming its file and field.

023 FR-003, FR-005 and SC-005. Two are about the declaration and two about the access row
that reaches it:

* a rate that is not exactly zero -- a balance that pays something is a **deposit**, whose
  rate, capitalisation, early-withdrawal penalty and interest taxation are the bank's terms
  and must be cited;
* a **missing** rate, which must not default to zero: *nobody said* and *the bank pays
  nothing* are different claims and only one of them is in the file;
* an ``[access.price]`` on a balance -- one hryvnia of balance costs one hryvnia, so a
  declared price would be one fact in two places;
* an ``[access.resale_price]``, for the same reason on the way out.

**Every case is a mutation of the shipped, valid pair**, on
``tests/contract/test_fund_declaration_loading.py``'s discipline: a battery written against
an invented template keeps passing after the real format moves underneath it.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.core.primitives.currency import Currency
from terezy.data.declarations import loader, resolver
from terezy.data.declarations.errors import DeclarationError
from tests import data_roots

CASH_FILE = data_roots.SHIPPED / "instruments" / "cash_uah_monobank.toml"
CASH_ID = "cash_uah_monobank"


def _is_comment(line: str) -> bool:
    return line.lstrip().startswith("#")


def _replace(text: str, old: str, new: str) -> str:
    """One textual edit to the first declaring line, refusing to silently do nothing."""
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if old in line and not _is_comment(line):
            lines[index] = line.replace(old, new, 1)
            return "".join(lines)
    pytest.fail(f"the shipped declaration no longer declares {old!r}; this test is stale")


def _drop_line(text: str, needle: str) -> str:
    lines = text.splitlines(keepends=True)
    matching = [line for line in lines if needle in line and not _is_comment(line)]
    assert len(matching) == 1, f"expected exactly one line declaring {needle!r}"
    return "".join(line for line in lines if line not in matching)


def _refused_declaration(tmp_path: Path, text: str) -> DeclarationError:
    target = tmp_path / "cash_uah_monobank.toml"
    target.write_text(text, encoding="utf-8")
    with pytest.raises(DeclarationError) as raised:
        loader.cash_from_file(target)
    return raised.value


def _root_quoting(tmp_path: Path, table: str) -> Path:
    """The shipped root with one price table appended to the cash access entry.

    Appended at the end of the entry rather than written into a fresh file, because the rule
    under test is the resolver's cross-file check: the price is refused for what the
    *instrument* is, which nothing reading the access file alone can know.
    """
    root = tmp_path / "data"
    shutil.copytree(data_roots.SHIPPED, root)
    access = root / "access" / "instruments.toml"
    lines = access.read_text(encoding="utf-8").splitlines(keepends=True)
    starts = next(
        index
        for index, line in enumerate(lines)
        if f'instrument_id = "{CASH_ID}"' in line and not _is_comment(line)
    )
    ends = next(
        (later for later in range(starts + 1, len(lines)) if lines[later].startswith("[[access]]")),
        len(lines),
    )
    lines.insert(ends, table)
    access.write_text("".join(lines), encoding="utf-8")
    return root


def _refused_access(root: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as raised:
        resolver.tuple_from_data_root(root, base_currency=Currency.UAH, scenario_id=None)
    return raised.value


PRICE_TABLE = """
  [access.price]
  per_unit     = 1.0
  currency     = "UAH"
  kind         = "venue_terms"
  source       = "a fixture that must never load"
  retrieved_on = "2026-09-02"
  verified_on  = ""
"""

RESALE_TABLE = PRICE_TABLE.replace("[access.price]", "[access.resale_price]")


def test_the_shipped_declaration_loads_and_states_a_rate_of_exactly_zero() -> None:
    """The premise every mutation below rests on, so a stale battery fails here first."""
    declared = loader.cash_from_file(CASH_FILE)
    assert declared.id == CASH_ID
    assert declared.rate == 0.0
    assert declared.rate_provenance.sources


def test_a_rate_that_is_not_zero_is_refused_as_a_deposit(tmp_path: Path) -> None:
    """FR-003. The refusal names what a paying balance would need, rather than accepting it."""
    text = _replace(CASH_FILE.read_text(encoding="utf-8"), "rate_pct = 0.0", "rate_pct = 4.5")
    error = _refused_declaration(tmp_path, text)
    assert error.field_path.endswith("rate_pct")
    assert "deposit" in error.problem


def test_a_missing_rate_is_refused_rather_than_defaulted_to_zero(tmp_path: Path) -> None:
    """FR-003. *Nobody said* and *the bank pays nothing* are different claims."""
    text = _drop_line(CASH_FILE.read_text(encoding="utf-8"), "rate_pct")
    error = _refused_declaration(tmp_path, text)
    assert "rate_pct" in error.field_path


def test_a_balance_that_quotes_a_unit_price_is_refused(tmp_path: Path) -> None:
    """FR-005. Sizing is identity, so a price here is one fact in two places."""
    error = _refused_access(_root_quoting(tmp_path, PRICE_TABLE))
    assert error.field_path.endswith("price")
    assert CASH_ID in error.problem


def test_a_balance_that_quotes_a_resale_price_is_refused(tmp_path: Path) -> None:
    """FR-005, the same rule on the way out."""
    error = _refused_access(_root_quoting(tmp_path, RESALE_TABLE))
    assert error.field_path.endswith("resale_price")
    assert CASH_ID in error.problem
