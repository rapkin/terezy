"""The two plugin interfaces are records of functions dispatched from a mapping.

Constitution Principle II caps the plugin interfaces at four; owner decision D-E says what
one *is*: "a plugin interface is a **function signature**, or a frozen record of functions
passed explicitly... Registries are mappings of functions, not subclass dispatch." This
feature implements two of the four, and this module asserts the shape rather than trusting
that nobody reintroduced a class hierarchy at the one place a hierarchy is tempting.

``abc`` is already blocked in ``core`` by ``.importlinter``, so the crudest violation
cannot compile. What that gate cannot see is a registry that dispatches on ``type()``, an
ops record that acquired behaviour, or a lookup that quietly falls back to a default when
a name is unrecognised -- and the last of those is the one that would do real damage,
because for a tax rule the comfortable default is "no tax".
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

import pytest

from terezy.core.instruments import fixed_income
from terezy.core.instruments import registry as instruments
from terezy.core.instruments.interface import InstrumentOps
from terezy.core.tax import flat_rate
from terezy.core.tax import registry as taxes
from terezy.core.tax.interface import TaxRuleOps

pytestmark = pytest.mark.contract


class TestTheRecordsAreDataNotObjects:
    """A frozen record whose fields happen to be functions, carrying no behaviour."""

    @pytest.mark.parametrize("record", [InstrumentOps, TaxRuleOps])
    def test_the_ops_record_is_a_frozen_dataclass(self, record: type) -> None:
        assert dataclasses.is_dataclass(record)
        assert record.__dataclass_params__.frozen  # type: ignore[attr-defined]

    @pytest.mark.parametrize("record", [InstrumentOps, TaxRuleOps])
    def test_the_ops_record_inherits_from_nothing(self, record: type) -> None:
        # No base class to inherit and no protocol to implement. A shared base is how a
        # missing case silently acquires a default, which is the failure mode Principle II
        # and FR-016 both exist to prevent.
        assert record.__bases__ == (object,)

    @pytest.mark.parametrize("record", [InstrumentOps, TaxRuleOps])
    def test_the_ops_record_carries_no_methods_of_its_own(self, record: type) -> None:
        # Only the dataclass machinery. Behaviour attached to a record is what owner
        # decision D-E rules out; a module is the namespace a class would otherwise be.
        assert [
            name
            for name, value in vars(record).items()
            if callable(value) and not name.startswith("__")
        ] == []

    def test_every_field_of_every_ops_record_is_a_function(self) -> None:
        for ops in (instruments.OPS, flat_rate.OPS):
            for field in dataclasses.fields(ops):
                assert callable(getattr(ops, field.name)), field.name


class TestDispatchIsAMapping:
    """A ``dict`` from a declared name to an implementation. Nothing scans subclasses."""

    def test_the_instrument_registry_is_a_mapping_of_ops_records(self) -> None:
        assert isinstance(instruments.REGISTRY, Mapping)
        assert all(isinstance(ops, InstrumentOps) for ops in instruments.REGISTRY.values())

    def test_the_tax_registry_is_a_mapping_of_ops_records(self) -> None:
        assert isinstance(taxes.REGISTRY, Mapping)
        assert all(isinstance(ops, TaxRuleOps) for ops in taxes.REGISTRY.values())

    def test_the_declared_instrument_class_selects_the_fixed_income_functions(self) -> None:
        ops = instruments.ops_for(instruments.FIXED_INCOME)
        assert ops.events is fixed_income.events
        assert ops.tax_classes is fixed_income.tax_classes
        assert ops.constraints is fixed_income.constraints


class TestAnUnknownNameIsAFailureNotAFallback:
    """The closed mapping is the contract; a missing key is never a default."""

    def test_an_unknown_instrument_class_fails_naming_what_is_known(self) -> None:
        with pytest.raises(KeyError, match="unknown instrument class") as raised:
            instruments.ops_for("crypto_perpetual")
        assert "fixed_income" in str(raised.value)

    def test_an_unknown_tax_rule_fails_naming_what_is_known(self) -> None:
        with pytest.raises(KeyError, match="unknown tax rule") as raised:
            taxes.ops_for("progressive_bands")
        assert "flat_rate" in str(raised.value)

    def test_there_is_no_exempt_rule_because_the_exemption_is_data(self) -> None:
        # If the exempt case needed its own rule the abstraction would be wrong, and it
        # would be wrong the moment a second exempt instrument appeared. The registry's
        # key set is the proof: one rule kind, covering a declared class of zeroes.
        assert set(taxes.REGISTRY) == {"flat_rate"}
