"""The cross-file pass: the two checks a per-file validator structurally cannot make.

``schema.py`` validates one document at a time, which is all pydantic can see. Two of
FR-016's rules span files and are therefore impossible there:

* **A duplicate identifier.** Each file is individually valid; together they declare two
  different things with one name, and whichever loaded second would win by accident of
  directory ordering. The error names **both** files, because knowing only one of them
  leaves the reader to find the other by hand.
* **A reference to an undeclared tax class.** An instrument's ``tax_classes`` table holds
  references; whether they resolve depends on the tax files. Unresolved is reported and
  **never read as an exemption** -- a missing rule and a declared zero are opposite
  claims, and only one of them is cited (Principle I). This is the single most expensive
  silent default available in this domain: it would make every after-tax figure flattering
  by exactly the tax that was not charged.

So the order is fixed and is the whole design: **parse every file individually first,
then resolve.** A resolver that loaded lazily could not report a duplicate at all, since
it would never hold both declarations at once.

A third check lives here for the same reason -- it needs both sides. An instrument may
reference a class that exists but whose ``applies_to`` does not cover the income kind it
was referenced for. The tax rule refuses such a charge at run time (*"the rule does not
cover this"* and *"the rule applied and the answer was zero"* are opposite claims), and
catching it here turns a refusal mid-projection into a message about the file that caused
it.

**No caching, no global registry.** :func:`resolve` takes the files it is to read and
returns a value. A module-level cache would make the second call in a process depend on
the first, which is exactly the hidden state that makes a determinism claim (C4)
unverifiable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from terezy.data.declarations import loader
from terezy.data.declarations.errors import DeclarationError

if TYPE_CHECKING:  # pragma: no cover -- typing only
    from collections.abc import Mapping, Sequence
    from pathlib import Path

    from terezy.core.instruments.interface import InstrumentDeclaration
    from terezy.core.tax.interface import TaxClass

INSTRUMENTS_DIR = "instruments"
"""Where instrument declarations live under a data root."""

TAX_DIR = "tax"
"""Where jurisdiction rule packs live under a data root."""


@dataclass(frozen=True, slots=True)
class Declarations:
    """Every declaration one run was given, resolved and keyed by id.

    A frozen record carrying only data, like everything else in the project. The two file
    maps are not decoration: they are what lets a *later* failure -- a manifest entry
    (FR-012), an unresolved reference discovered downstream -- still name the file a
    declaration came from, after the TOML has long since been discarded.
    """

    instruments: Mapping[str, InstrumentDeclaration]
    """Declared instruments by id. Every ``tax_classes`` reference in here resolves
    against :attr:`tax_classes`; that is checked before this record exists."""

    tax_classes: Mapping[str, TaxClass]
    """Declared tax classes by id, ready to pass to ``results.project`` as the tax pack."""

    instrument_files: Mapping[str, Path]
    """Which file declared each instrument."""

    tax_class_files: Mapping[str, Path]
    """Which file declared each tax class."""


def _refuse_duplicate(
    kind: str,
    identifier: str,
    field_path: str,
    already: Path,
    now: Path,
) -> DeclarationError:
    """The duplicate-id error, naming both files. Built here so both callers agree.

    Returned rather than raised so the raise stays at the call site, where the reader can
    see which loop found the collision.
    """
    return DeclarationError(
        now,
        field_path,
        f"declares the {kind} id {identifier!r}, which is already declared by "
        f"{already}. Two declarations with one id are not merged and neither is "
        "preferred: whichever loaded last would win by accident of directory ordering, "
        "and every figure would silently describe the wrong one.",
        f"rename one of the two {kind}s, or delete the file that is a duplicate",
    )


def resolve(
    *,
    instrument_files: Sequence[Path],
    tax_files: Sequence[Path],
) -> Declarations:
    """Parse every file, then check what only the whole set can show.

    Files are read in the order given and the caller is expected to have sorted them
    (:func:`from_data_root` does), so that a duplicate is always reported against the same
    one of the two files rather than depending on filesystem iteration order.
    """
    tax_classes: dict[str, TaxClass] = {}
    tax_class_files: dict[str, Path] = {}
    for path in tax_files:
        for declared in loader.tax_classes_from_file(path):
            if declared.id in tax_classes:
                raise _refuse_duplicate(
                    "tax class",
                    declared.id,
                    f"jurisdiction.tax_class[{declared.id}].id",
                    tax_class_files[declared.id],
                    path,
                )
            tax_classes[declared.id] = declared
            tax_class_files[declared.id] = path

    instruments: dict[str, InstrumentDeclaration] = {}
    instrument_files_by_id: dict[str, Path] = {}
    for path in instrument_files:
        declaration = loader.instrument_from_file(path)
        if declaration.id in instruments:
            raise _refuse_duplicate(
                "instrument",
                declaration.id,
                "instrument.id",
                instrument_files_by_id[declaration.id],
                path,
            )
        instruments[declaration.id] = declaration
        instrument_files_by_id[declaration.id] = path

    for identifier, declaration in instruments.items():
        _check_references(
            declaration,
            tax_classes,
            path=instrument_files_by_id[identifier],
        )

    return Declarations(
        instruments=instruments,
        tax_classes=tax_classes,
        instrument_files=instrument_files_by_id,
        tax_class_files=tax_class_files,
    )


def _check_references(
    declaration: InstrumentDeclaration,
    tax_classes: Mapping[str, TaxClass],
    *,
    path: Path,
) -> None:
    """Every tax class an instrument names must exist **and** cover the kind named.

    Both halves matter, and the second is the easier one to get wrong. A class that exists
    but does not apply to the income kind it was referenced for would pass a naive
    existence check and then be refused by the tax rule mid-projection -- reported against
    an event rather than against the file that declared the reference.
    """
    for kind, class_id in declaration.tax_classes.items():
        field_path = f"instrument.tax_classes.{kind.value}"
        declared = tax_classes.get(class_id)
        if declared is None:
            raise DeclarationError(
                path,
                field_path,
                f"{declaration.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which no tax file declares. The reference is reported "
                "rather than treated as untaxed: an exemption is a cited claim and a "
                "missing rule is not, and reading the second as the first would flatter "
                "every figure derived from this instrument by exactly the tax that was "
                "never charged.",
                f"declare {class_id!r} in a data/tax file, or reference a class that exists"
                f" ({', '.join(sorted(tax_classes)) or 'none are declared'})",
            )
        if kind not in declared.applies_to:
            raise DeclarationError(
                path,
                field_path,
                f"{declaration.id!r} taxes its {kind.value!r} income under the class "
                f"{class_id!r}, which declares that it applies to "
                f"{', '.join(sorted(applies.value for applies in declared.applies_to))} "
                "and not to that kind. A class asked to charge a kind outside its own "
                "scope refuses rather than charging zero, so the reference would fail "
                "mid-projection instead of here.",
                f"add {kind.value!r} to that class's applies_to if the rule covers it, or "
                "reference the class that does",
            )


def from_data_root(root: Path) -> Declarations:
    """Every declaration under a data root: ``instruments/*.toml`` and ``tax/*.toml``.

    Sorted, so a run is reproducible: an unsorted directory listing would make the order
    of two files -- and therefore which one a duplicate-id error names -- depend on the
    filesystem.

    Only the top level of each directory is read. ``instruments/nav/`` holds dated NAV and
    distribution series, which are a different shape and a different feature; globbing
    recursively would try to validate them as declarations and report a confusing failure
    about a file that is perfectly correct.

    An empty directory is an **error**, not an empty world. Silently returning no
    declarations would make a mistyped path indistinguishable from a repository with no
    data, and every downstream reference would then fail for a reason that names the
    wrong thing.
    """
    instruments = sorted((root / INSTRUMENTS_DIR).glob("*.toml"))
    tax = sorted((root / TAX_DIR).glob("*.toml"))
    for directory, found in ((INSTRUMENTS_DIR, instruments), (TAX_DIR, tax)):
        if not found:
            raise DeclarationError(
                root / directory,
                "",
                f"contains no *.toml declarations. An empty {directory} directory is "
                "reported rather than read as 'nothing is declared': the two are "
                "indistinguishable to everything downstream, and one of them is a "
                "mistyped path.",
                "check the data root, or add a declaration file",
            )
    return resolve(instrument_files=instruments, tax_files=tax)
