"""The run manifest: what fed a run, which version of it, and the digest of what came out.

*"Every run emits a manifest: scenario hash, code version, objective, seed, and the
version and provenance of every input series and data file. **A result without a manifest
is not a result**"* (constitution, Principle III). FR-012 says the same thing from the
other side: *"a projection MUST be reproducible: the same inputs MUST produce identical
results, and each result MUST record the inputs and their versions."*

**Why the digest lives here and not in ``core``.** Hashing requires serialisation, and
``core`` is barred from serialisation modules -- ``hashlib`` sits in its forbidden-imports
list in ``.importlinter`` beside ``json``, ``pickle`` and ``tomllib``, so this module is
the only place in the project entitled to import it. What stays in the core is the part
that has to be a *domain* decision: which facts a result is identified by, and how each
one is rendered unambiguously (``core.ledger.canonical``, ``core.results.canonical``).
Those functions return nested tuples of primitives and encode nothing. This module turns
such a tuple into bytes and those bytes into a digest, and makes no judgement about what
belongs in it.

**The digest asserts bit-identity** (research.md D5). Amounts reach here already rendered
by ``float.hex()``, so two runs agree only if every amount agrees to the last bit. That is
deliberately *stricter* than the project tolerance: the tolerance exists because
hand-computed arithmetic and float arithmetic differ, whereas determinism means the same
code on the same inputs must produce the same bits. A digest over a rounded rendering would
mask any nondeterminism smaller than the rounding unit -- precisely the bug C4 exists to
find. The two are never conflated: nothing in this module imports the tolerance, and
nothing in it rounds.

**What exactly gets encoded, and why the encoding is spelled out rather than delegated.**
:func:`encode` is a self-delimiting, type-tagged byte scheme written by hand:

* ``None`` -> ``n;``
* an integer -> ``i<decimal>;``
* a string -> ``s<byte length>:<utf-8 bytes>;``
* a tuple -> ``t<element count>:<encoded elements>;``

Every string carries its length and every tuple its element count, so no two different
structures can produce the same bytes: ``("a", "b")`` cannot collide with ``("ab",)``, an
empty tuple cannot collide with a tuple containing one, and ``"1"`` cannot collide with
``1``. That injectivity is the whole value of the digest -- a collision is not a hash
accident but two genuinely different results reported as one. ``repr`` would be shorter and
is not injective in any documented way; ``json`` would work and is forbidden here for a
better reason than layering, namely that it would silently accept a ``float`` and decide
its own rendering.

The encoded bytes are prefixed with :data:`ENCODING`, so a digest names the scheme it was
taken under. Without that, changing the encoding would silently invalidate every digest
ever recorded, and an older manifest would look like a run that produced different
numbers.

**How the version of a declaration is identified.** No declaration file carries a
``version`` field, and none is added here: a hand-maintained version number is one a
maintainer must remember to bump, and the failure mode is a file that changed while
claiming not to have. The version recorded is instead the **SHA-256 of the file's bytes**
(:func:`file_version`), which cannot go stale, is exactly what git already tracks, and
answers the only question a manifest is asked later -- *was the run fed this file, or a
different one?* A file is named by ``directory/name`` rather than by its full path, for the
same reason ``loader.source_id`` does: an absolute path embeds one machine's layout, and
two checkouts of the same commit would then describe the same declaration differently.

**Why the manifest names every declaration the run was given, not only the one projected.**
Reproducing a run needs the whole input set, because the set is what resolution depended
on: another file declaring the same id would have been a load-time failure, and one
declaring the tax class that was used is as load-bearing as the instrument itself. The
instrument actually projected is named separately
(:attr:`RunManifest.projected_instrument_id`) so nothing has to be inferred from the list.

**The manifest records the unverified sources; the digest does not.** Provenance is
excluded from the canonical form on purpose -- filling in a ``verified_on`` changes what a
result *says about its sources* and moves no computed amount, so a digest that included it
would fail C4 on a documentation edit. That exclusion is not permission to lose the fact:
:attr:`RunManifest.unverified_sources` names every source behind the figure that has never
been checked against a primary source, so FR-015's mark survives at the manifest level too.
The digest answers *"is this the same arithmetic?"*; the manifest answers *"what did it
rest on?"*.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal, assert_never

import terezy
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger.canonical import Canonical
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance
from terezy.core.results import canonical
from terezy.core.results.project import Projection
from terezy.data.declarations.errors import DeclarationError
from terezy.data.declarations.resolver import Declarations

ENCODING: Final = "terezy-canonical-v3"
"""The name of the byte encoding a digest was taken under.

Prefixed into every encoding, so a digest is comparable only against digests of the same
scheme. Bump it when :func:`encode` changes shape; every previously recorded digest then
visibly belongs to a different scheme instead of silently disagreeing. The pinned pair in
``tests/unit/test_results_canonical.py`` (``CANONICAL_SHAPE_BY_ENCODING``) makes a shape
change under an unchanged tag a red test rather than a discovery.

**v2** (2026-08): feature 002 gave the canonical event tuple ``capacity_pool`` and the
ledger form the capacity accumulator, so a v1 digest of the same ledger no longer agrees
with one taken here -- the tag says so instead of letting the two disagree under one name.

**v3** (2026-08): feature 007 filled the reserved real-terms slot. Where v2 rendered the slot
as one ``(tag, value)`` pair, v3 renders two figures -- realized and assumed -- each carrying
its basis, the series it is real against and the window it covers. No nominal figure, no
schedule row and no tax charge moved; the tag moves because the *form* did, and a v2 digest
of the same projection would otherwise silently disagree under an unchanged name.
"""

ALGORITHM: Final = "sha256"
"""The digest algorithm, named in the digest string itself.

Carried in the value rather than only in this constant so that a stored digest cannot be
compared against one taken with a different algorithm by accident.
"""

InputKind = Literal["instrument", "tax_class"]
"""What kind of declaration an :class:`InputRef` describes. A closed set, not a free string."""


def encode(value: Canonical) -> bytes:
    """One canonical value as unambiguous bytes, prefixed with the encoding's name.

    See the module docstring for the scheme and for why it is written out rather than
    delegated to a serialisation library.
    """
    return ENCODING.encode("utf-8") + b"\x00" + _encode(value)


def _encode(value: Canonical) -> bytes:
    """The recursive half of :func:`encode`, without the scheme prefix."""
    if isinstance(value, bool):
        # ``bool`` is a subclass of ``int`` in Python, so ``True`` would encode exactly as
        # ``1``. The canonical form's type does not admit a boolean and the type checker
        # says so, but a silent collision between a flag and a count is the precise class
        # of confusion a digest exists to rule out, so it is refused at runtime as well.
        raise TypeError(
            f"{value!r} is a boolean, which the canonical form does not contain. Encoding "
            "it would make it indistinguishable from the integer of the same value, and "
            "two different results would digest identically."
        )
    match value:
        case None:
            return b"n;"
        case int():
            return b"i" + str(value).encode("ascii") + b";"
        case str():
            raw = value.encode("utf-8")
            return b"s" + str(len(raw)).encode("ascii") + b":" + raw + b";"
        case tuple():
            body = b"".join(_encode(item) for item in value)
            return b"t" + str(len(value)).encode("ascii") + b":" + body + b";"
        case _:  # pragma: no cover -- mypy proves this unreachable
            assert_never(value)


def digest(value: Canonical) -> str:
    """The digest of one canonical value, as ``"sha256:<hex>"``.

    Self-describing rather than a bare hex string, so a recorded digest carries both the
    algorithm that produced it and -- through :func:`encode` -- the scheme it was taken
    over.
    """
    return f"{ALGORITHM}:{hashlib.sha256(encode(value)).hexdigest()}"


def digest_of_projection(result: Projection) -> str:
    """The digest of a whole projection: its ledger, schedule, charges and figures.

    The one-line composition C4 and SC-006 compare. It is a function of the canonical form
    alone, so anything the canonical form omits -- provenance -- cannot move it.
    """
    return digest(canonical.of_projection(result))


def file_version(path: Path) -> str:
    """The version of one declaration file: the digest of its bytes.

    Read as bytes rather than as text so that a change to the file's line endings or its
    encoding counts as a change. It is a different file; a version that said otherwise
    would be answering a question nobody asked.
    """
    try:
        content = path.read_bytes()
    except OSError as exc:
        raise DeclarationError(
            path,
            "",
            f"could not be read while recording the run manifest: {exc}. A manifest that "
            "omitted the file would claim the run rested on inputs nobody can identify, "
            "which is the same as having no manifest at all.",
            "check that the file still exists and is readable",
        ) from exc
    return f"{ALGORITHM}:{hashlib.sha256(content).hexdigest()}"


def file_name(path: Path) -> str:
    """A declaration file's name for the record: ``directory/name``, never the full path.

    The same choice ``loader.source_id`` makes, for the same reason: an absolute path
    embeds one machine's directory layout, so two checkouts of the same commit would
    describe the same declaration differently and two manifests of the same run would not
    compare. The parent directory is kept because ``instruments/ua.toml`` and
    ``tax/ua.toml`` are different files.
    """
    return f"{path.parent.name}/{path.name}"


@dataclass(frozen=True, slots=True)
class InputRef:
    """One declaration a run was given: what it is, where it came from, which version."""

    kind: InputKind
    """Whether this is an instrument or a tax class. A closed set (:data:`InputKind`)."""

    id: str
    """The declared id, as every figure and every reference names it."""

    file: str
    """``directory/name`` of the declaring file. See :func:`file_name`."""

    version: str
    """``"sha256:<hex>"`` of the file's bytes. See the module docstring on versions."""

    unverified_sources: tuple[str, ...]
    """Ids of this declaration's sources with no verification date, sorted.

    Empty when every source behind the declaration has been checked against a primary
    source. Recorded per input rather than only in the roll-up so that a reader can see
    *which file* is the one still to verify.
    """


@dataclass(frozen=True, slots=True)
class RunManifest:
    """Everything needed to say what a run was, and to recognise its output again.

    Every field is required. There is no default anywhere in this record, which is the
    executable form of *"a result without a manifest is not a result"*: a manifest cannot
    be built by omitting the awkward half of it.
    """

    code_version: str
    """The version of ``terezy`` that produced the run."""

    encoding: str
    """The canonical encoding the digest was taken under. See :data:`ENCODING`."""

    owner_id: str
    """Whose run this was. Present from day one per Principle VII."""

    projected_instrument_id: str
    """Which declared instrument was projected, of the ones :attr:`inputs` lists."""

    holding: Holding
    """The purchase, recorded as the record itself rather than as a summary.

    FR-012 asks the result to record its inputs; the inputs are small, frozen and already
    typed, so storing them beats storing a rendering of them that could disagree.
    """

    horizon: DateRange
    """The window the run was asked about."""

    assumptions: Assumptions
    """The modelling choices the run was given -- consumption method, coupon policy."""

    inputs: tuple[InputRef, ...]
    """Every declaration the run was given, sorted by kind and id.

    Every one, not only the projected instrument. See the module docstring.
    """

    seed: int | None
    """The seed of any stochastic path, or ``None`` where the run had none.

    Required rather than defaulted, so ``None`` is a statement that this run's arithmetic
    is deterministic end to end and not an unset field. Feature 001 contains no randomness
    at all -- the core may not import ``random`` -- so it is ``None`` here, and the field
    exists because Principle III requires a recorded seed the moment one exists.
    """

    result_digest: str
    """``"sha256:<hex>"`` over the canonical form of the projection (:func:`digest`)."""

    unverified_sources: tuple[str, ...]
    """Ids of every source behind the headline figure with no verification date, sorted.

    The roll-up of what :attr:`inputs` records per file, taken from the figure's own
    provenance so it describes what the *result* rests on rather than what happened to be
    loaded. Non-empty is the expected state for feature 001 (FR-014, FR-015).
    """


def input_refs(declarations: Declarations) -> tuple[InputRef, ...]:
    """Every declaration in a resolved set, as manifest input references.

    Sorted by ``(kind, id)`` rather than left in load order. Load order is directory order,
    which is a property of the filesystem, and a manifest whose field order depended on it
    would differ between two machines that ran the same scenario.
    """
    instruments = [
        InputRef(
            kind="instrument",
            id=identifier,
            file=file_name(declarations.instrument_files[identifier]),
            version=file_version(declarations.instrument_files[identifier]),
            unverified_sources=_unverified_ids(_instrument_provenance(declaration)),
        )
        for identifier, declaration in declarations.instruments.items()
    ]
    tax_classes = [
        InputRef(
            kind="tax_class",
            id=identifier,
            file=file_name(declarations.tax_class_files[identifier]),
            version=file_version(declarations.tax_class_files[identifier]),
            unverified_sources=_unverified_ids(declared.provenance),
        )
        for identifier, declared in declarations.tax_classes.items()
    ]
    return tuple(sorted([*instruments, *tax_classes], key=lambda ref: (ref.kind, ref.id)))


def _instrument_provenance(declaration: InstrumentDeclaration) -> Provenance:
    """Every source behind one instrument declaration: its terms and its constraints.

    Both, because they are two observations from two sources -- a minimum ticket and a
    coupon rate are different facts -- and a manifest that recorded only the terms would
    call a file verified while half of it was not.
    """
    return prov.merge(declaration.terms.provenance, declaration.constraints.provenance)


def _unverified_ids(provenance: Provenance) -> tuple[str, ...]:
    """The ids of the sources responsible for an unverified mark, sorted."""
    return tuple(sorted(ref.id for ref in prov.unverified_sources(provenance)))


def of_run(
    *,
    result: Projection,
    declarations: Declarations,
    holding: Holding,
    horizon: DateRange,
    assumptions: Assumptions,
    seed: int | None,
) -> RunManifest:
    """The manifest of one projection: its inputs, their versions, and its digest.

    Every argument is required and keyword-only. There is nothing this function can
    reasonably guess: a manifest built from defaults would be a record of a run that did
    not happen, which is worse than no record.

    Raises ``ValueError`` when the holding names an instrument the declaration set does not
    contain. That is a programmer error rather than a fact about the money -- the resolver
    has already refused any unresolvable reference -- and a manifest naming inputs that did
    not feed the run would be a false record rather than an incomplete one.
    """
    if holding.instrument_id not in declarations.instruments:
        raise ValueError(
            f"the holding names instrument {holding.instrument_id!r}, which is not in the "
            f"declaration set this run was given ({sorted(declarations.instruments)}). A "
            "manifest cannot record inputs that did not feed the run."
        )
    return RunManifest(
        code_version=terezy.__version__,
        encoding=ENCODING,
        owner_id=holding.owner_id,
        projected_instrument_id=holding.instrument_id,
        holding=holding,
        horizon=horizon,
        assumptions=assumptions,
        inputs=input_refs(declarations),
        seed=seed,
        result_digest=digest_of_projection(result),
        unverified_sources=_unverified_ids(result.hurdle.provenance),
    )
