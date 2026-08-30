"""SC-006: every broken scheme declaration fails at load, naming the file and the field.

A battery rather than a handful, because SC-006 is a claim about *every* way a file can be
wrong and a sampled version goes stale the first time somebody adds a field.

**Two cases are this feature's own.**

*A rate written on a periodic component, or an amount on a rate component.* There is no
``rate_pct`` key on a periodic component and no ``amount`` on a rate component, so FR-019's
confusion is an unrecognised field rather than a case the loader has to remember to reject.

*A recorded context with no reason it is not applied.* A cited fact declared beside a
schedule and silently not applied is indistinguishable from an oversight; the field that
says why is required, which is what FR-008a is actually asking for.

**Every case asserts on the error's own ``field_path`` and ``problem``, never on ``str(error)``.**
The rendered string begins with the file path, and pytest names ``tmp_path`` after the test
that asked for it -- so ``assert "amount" in str(error)`` inside
``test_an_amount_on_a_rate_component_...`` passes on the directory name alone. Two cases here
did exactly that.

The shipped files are loaded in ``test_crediting_destination_loading.py``, which resolves the
whole data root; a battery of broken ones proves nothing about them.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from terezy.core.primitives import provenance as prov
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.money import Money
from terezy.core.tax import scheme as schemes
from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

pytestmark = pytest.mark.contract

HEADER = """
[scheme]
id                = "xx_scheme"
name              = "SYNTHETIC FIXTURE -- an invented taxation scheme"
jurisdiction      = "xx"
tax_currency      = "UAH"
variant           = "synthetic_variant"
reporting_cadence = "quarterly"
declared_for      = "stream"
"""

RATE_COMPONENT = """
  [[scheme.rate_component]]
  id   = "{id}"
  name = "SYNTHETIC синтетичний збір"
"""

RATE_ENTRY = """
    [[scheme.rate_component.rate]]
    effective_from = "{effective_from}"
    rate_pct       = {rate_pct}
    note           = "SYNTHETIC FIXTURE."
    kind           = "tax_rule"
    source         = "SYNTHETIC FIXTURE -- an invented rate."
    retrieved_on   = "2026-08-30"
    verified_on    = ""
"""

CONTEXT = """
    [[scheme.rate_component.context]]
    id                  = "recorded_not_applied"
    statement           = "SYNTHETIC FIXTURE -- an invented provision."
    not_applied_because = "{not_applied_because}"
    kind                = "tax_rule"
    source              = "SYNTHETIC FIXTURE -- an invented provision."
    retrieved_on        = "2026-08-30"
    verified_on         = ""
"""

PERIODIC_COMPONENT = """
  [[scheme.periodic_component]]
  id     = "{id}"
  name   = "SYNTHETIC синтетичний внесок"
  period = "{period}"
"""

AMOUNT_ENTRY = """
    [[scheme.periodic_component.amount]]
    effective_from = "{effective_from}"
    amount         = {amount}
    currency       = "UAH"
    note           = "SYNTHETIC FIXTURE."
    kind           = "tax_rule"
    source         = "SYNTHETIC FIXTURE -- an invented statutory sum."
    retrieved_on   = "2026-08-30"
    verified_on    = ""
"""


def _body() -> str:
    return (
        HEADER
        + RATE_COMPONENT.format(id="levy")
        + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=1.0)
        + PERIODIC_COMPONENT.format(id="contribution", period="month")
        + AMOUNT_ENTRY.format(effective_from="2026-01-01", amount=0.0)
    )


def _file(tmp_path: Path, body: str, *, name: str = "xx.toml") -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _load_error(path: Path) -> DeclarationError:
    with pytest.raises(DeclarationError) as caught:
        loader.scheme_from_file(path)
    return caught.value


def test_the_control_case_loads_so_every_refusal_below_is_about_one_change(
    tmp_path: Path,
) -> None:
    scheme = loader.scheme_from_file(_file(tmp_path, _body()))

    assert scheme.id == "xx_scheme"
    assert scheme.tax_currency is Currency.UAH
    assert scheme.declared_for == "stream"
    assert [component.id for component in scheme.rate_components] == ["levy"]
    assert scheme.rate_components[0].schedule[0].rate == 0.01
    assert scheme.periodic_components[0].schedule[0].amount.amount == 0.0
    stamped = {
        ref.kind
        for component in scheme.rate_components
        for entry in component.schedule
        for ref in entry.provenance.sources
    }
    assert stamped == {"tax_rule"}


class TestOneFileReadInIsolation:
    def test_an_unrecognised_field_is_refused(self, tmp_path: Path) -> None:
        error = _load_error(_file(tmp_path, _body() + '\nnote_to_self = "hello"\n'))

        assert "note_to_self" in str(error)

    def test_a_missing_verified_on_is_refused_rather_than_defaulted(self, tmp_path: Path) -> None:
        """Empty is a state; absent is an oversight, and the two must not look alike."""
        error = _load_error(_file(tmp_path, _body().replace('verified_on    = ""', "", 1)))

        assert error.field_path.endswith(".verified_on")
        assert "missing" in error.problem.lower()

    def test_a_scheme_charging_no_component_at_all_is_refused(self, tmp_path: Path) -> None:
        error = _load_error(_file(tmp_path, HEADER))

        assert error.field_path == "scheme"
        assert "declares no component at all" in error.problem

    def test_a_rate_component_with_an_empty_schedule_is_refused(self, tmp_path: Path) -> None:
        """``rate = []`` is a component that charges nothing on every date and says so
        nowhere -- the silent zero this whole feature exists to refuse."""
        body = HEADER + RATE_COMPONENT.format(id="levy") + "  rate = []\n"
        error = _load_error(_file(tmp_path, body))

        assert error.field_path == "scheme.rate_component[levy].rate"
        assert "declares no rate at all" in error.problem

    def test_a_rate_component_with_no_schedule_key_at_all_is_refused(self, tmp_path: Path) -> None:
        """A different refusal from the empty one, and from a different layer.

        The shape validation reports the missing key; the loader reports an empty list. Both
        must fire, because giving the field a ``= []`` default -- the defaulting the schema
        header forbids -- would collapse the first into the second with nothing to say so.
        """
        error = _load_error(_file(tmp_path, HEADER + RATE_COMPONENT.format(id="levy")))

        assert error.field_path == "scheme.rate_component[0].rate"
        assert "missing" in error.problem.lower()

    def test_two_entries_on_one_effective_date_are_refused(self, tmp_path: Path) -> None:
        body = _body() + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=2.0)
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".effective_from")
        assert "for the second time" in error.problem

    def test_a_schedule_running_backwards_is_refused_rather_than_sorted(
        self, tmp_path: Path
    ) -> None:
        """A file whose order disagrees with its dates is one a human misreads."""
        body = (
            HEADER
            + RATE_COMPONENT.format(id="levy")
            + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=1.0)
            + RATE_ENTRY.format(effective_from="2024-01-01", rate_pct=2.0)
        )
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".effective_from")
        assert "before the previous entry's 2025-01-01" in error.problem

    def test_a_negative_rate_is_refused(self, tmp_path: Path) -> None:
        body = (
            HEADER
            + RATE_COMPONENT.format(id="levy")
            + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=-1.0)
        )
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".rate_pct")
        assert "is -1.0" in error.problem

    def test_a_negative_amount_is_refused(self, tmp_path: Path) -> None:
        body = (
            HEADER
            + PERIODIC_COMPONENT.format(id="contribution", period="month")
            + AMOUNT_ENTRY.format(effective_from="2026-01-01", amount=-5.0)
        )
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".amount")
        assert "is -5.0" in error.problem

    def test_two_components_sharing_one_id_are_refused(self, tmp_path: Path) -> None:
        body = (
            _body()
            + RATE_COMPONENT.format(id="levy")
            + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=3.0)
        )
        error = _load_error(_file(tmp_path, body))

        # The field path names a table the file actually has, and the message names both
        # positions the duplicate is written in.
        assert error.field_path == "scheme.rate_component[levy].id"
        assert "scheme.rate_component[levy] and scheme.rate_component[levy]" in error.problem

    def test_a_rate_component_and_a_periodic_one_may_not_share_an_id(self, tmp_path: Path) -> None:
        body = (
            HEADER
            + RATE_COMPONENT.format(id="same")
            + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=1.0)
            + PERIODIC_COMPONENT.format(id="same", period="month")
            + AMOUNT_ENTRY.format(effective_from="2026-01-01", amount=0.0)
        )
        error = _load_error(_file(tmp_path, body))

        # Across BOTH kinds, and the message names both tables: `component_standing` looks a
        # component up by id alone, so a rate component and a periodic one sharing one would
        # make which of them answered depend on scan order.
        assert error.field_path == "scheme.rate_component[same].id"
        assert "scheme.rate_component[same] and scheme.periodic_component[same]" in error.problem

    def test_an_unknown_period_is_refused_and_the_refusal_lists_what_would_work(
        self, tmp_path: Path
    ) -> None:
        body = (
            HEADER
            + PERIODIC_COMPONENT.format(id="contribution", period="quarter")
            + AMOUNT_ENTRY.format(effective_from="2026-01-01", amount=0.0)
        )
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".period")
        assert "is 'quarter'" in error.problem
        assert error.remedy == "use one of: month"

    def test_an_unknown_declared_for_is_refused(self, tmp_path: Path) -> None:
        error = _load_error(
            _file(
                tmp_path,
                _body().replace('declared_for      = "stream"', 'declared_for      = "anyone"'),
            )
        )

        assert error.field_path == "scheme.declared_for"
        assert "is 'anyone'" in error.problem

    def test_an_unknown_currency_is_refused(self, tmp_path: Path) -> None:
        error = _load_error(
            _file(
                tmp_path, _body().replace('tax_currency      = "UAH"', 'tax_currency      = "XXX"')
            )
        )

        assert error.field_path == "scheme.tax_currency"
        assert "declares 'XXX'" in error.problem

    def test_a_recorded_context_with_no_reason_it_is_not_applied_is_refused(
        self, tmp_path: Path
    ) -> None:
        """A fact declared and silently not applied is indistinguishable from an oversight."""
        body = _body() + CONTEXT.format(not_applied_because="")
        error = _load_error(_file(tmp_path, body))

        assert error.field_path.endswith(".not_applied_because")
        assert "indistinguishable from an oversight" in error.problem

    def test_a_recorded_context_loads_and_is_not_applied(self, tmp_path: Path) -> None:
        body = (
            HEADER
            + RATE_COMPONENT.format(id="levy")
            + RATE_ENTRY.format(effective_from="2025-01-01", rate_pct=1.0)
            + CONTEXT.format(not_applied_because="it is conditioned on an event, not a date")
        )
        scheme = loader.scheme_from_file(_file(tmp_path, body))

        recorded = scheme.rate_components[0].context
        assert [item.id for item in recorded] == ["recorded_not_applied"]
        assert recorded[0].provenance.sources
        charge = schemes.charge_income(
            scheme,
            Money(100.0, Currency.UAH, prov.EMPTY),
            on_date=date(2099, 1, 1),
            series=None,
        )
        assert isinstance(charge, schemes.SchemeCharge), charge
        assert charge.lines[0].rate == 0.01

    def test_an_amount_on_a_rate_component_is_an_unrecognised_field(self, tmp_path: Path) -> None:
        """FR-019's confusion is unspellable rather than rejected by a remembered check.

        The rate entry keeps its own ``rate_pct`` so the *only* thing wrong with the file is
        the extra key -- writing ``amount`` in place of it plants a missing field as well, and
        the shape validation reports that one first.
        """
        body = _body().replace(
            "    rate_pct       = 1.0", "    rate_pct       = 1.0\n    amount         = 1.0"
        )
        error = _load_error(_file(tmp_path, body))

        assert "amount" in error.field_path
        assert "is not a field this loader recognises" in error.problem

    def test_a_rate_on_a_periodic_component_is_an_unrecognised_field(self, tmp_path: Path) -> None:
        body = _body().replace(
            "    amount         = 0.0", "    amount         = 0.0\n    rate_pct       = 0.0"
        )
        error = _load_error(_file(tmp_path, body))

        assert "rate_pct" in error.field_path
        assert "is not a field this loader recognises" in error.problem
