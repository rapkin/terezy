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
instrument actually projected is named separately (:attr:`ProjectedRun.instrument_id`) so
nothing has to be inferred from the list. An **answer** projects many and names none there:
its :attr:`RunManifest.projection` is ``None``.

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
from datetime import date
from pathlib import Path
from typing import Final, Literal, assert_never

import terezy
from terezy.core.instruments.access import InstrumentAccess
from terezy.core.instruments.fund import FundDeclaration
from terezy.core.instruments.interface import (
    Assumptions,
    DateRange,
    Holding,
    InstrumentDeclaration,
)
from terezy.core.ledger.canonical import Canonical
from terezy.core.primitives import provenance as prov
from terezy.core.primitives.provenance import Provenance
from terezy.core.primitives.rates import RealRate
from terezy.core.results import canonical
from terezy.core.results.answer import Answer, Refused
from terezy.core.results.project import Projection
from terezy.core.results.question import Question
from terezy.core.routes.legs import Route
from terezy.core.tax.interface import TaxClass
from terezy.data.declarations import resolver
from terezy.data.declarations.errors import DeclarationError
from terezy.data.declarations.resolver import (
    Declarations,
    InflationDeclarations,
    OfficialRateDeclarations,
)

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

InputKind = Literal[
    "access",
    "candidate_ceiling",
    "channel",
    "composition",
    "cpi_series",
    "early_exit_assumption",
    "fund",
    "group_vocabulary",
    "inflation_assumption",
    "instrument",
    "observation_kind",
    "official_rate",
    "question",
    "route",
    "scenario",
    "spendable",
    "stream",
    "tax_class",
    "venue",
]
"""What kind of declaration an :class:`InputRef` describes. A closed set, not a free string.

⚙ ``"fund"`` joined with feature 006. Kept distinct from ``"instrument"`` rather than folded
into it: the two are different declarations in the same directory, and a manifest that
called them one thing would hide which kind of file a run was actually fed.

⚙ ``"cpi_series"`` and ``"inflation_assumption"`` joined with feature 007. FR-015 requires the
manifest to record *which* inflation declaration produced a result -- two runs differing only
in their declared belief are two results, and a manifest that did not name the belief could
not tell them apart. The CPI series is recorded for the same reason from the other side: a
real figure is only reproducible if the manifest says which series deflated it, at which
version.

``"official_rate"`` is kept distinct from ``"cpi_series"`` although both are dated observation
series: a tax base struck at an official rate is only reproducible if the manifest says which
*legal* series struck it, and a manifest that called the two one thing could not.

Listed alphabetically because :func:`input_refs` sorts by ``(kind, id)``, so the order here is
the order a manifest reads in.

Widened by feature 015 from the five a single projection reads to every family an **answer**
reads, because SC-008 requires the manifest to name every file the run read: a run that read a
route, an access entry and a question and recorded none of them is a result that does not trace
to what produced it, which Principle III says is not a result.

**A member nothing constructs is not in the set.** An unreachable kind reads as coverage the
manifest does not have, which is the shape of claim the walk exists to make impossible.
"""


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
    """What sort of declaration this is. A closed set (:data:`InputKind`)."""

    id: str
    """The declared id, as every figure and every reference names it."""

    file: str
    """``directory/name`` of the declaring file, or the bare name for one at the data root.

    See :func:`file_name`, and :func:`_ref`'s ``at_root`` for why the parent is dropped there.
    """

    version: str
    """``"sha256:<hex>"`` of the file's bytes. See the module docstring on versions."""

    unverified_sources: tuple[str, ...]
    """Ids of this declaration's sources with no verification date, sorted.

    Empty when every source behind the declaration has been checked against a primary
    source. Recorded per input rather than only in the roll-up so that a reader can see
    *which file* is the one still to verify.
    """


@dataclass(frozen=True, slots=True)
class ProjectedRun:
    """What a run of a *single* projection was: one holding, one window, one set of choices."""

    instrument_id: str
    """Which declared instrument was projected, of the ones :attr:`RunManifest.inputs` lists."""

    holding: Holding
    """The purchase, recorded as the record itself rather than as a summary.

    FR-012 asks the result to record its inputs; the inputs are small, frozen and already
    typed, so storing them beats storing a rendering of them that could disagree.
    """

    horizon: DateRange
    """The window the run was asked about."""

    assumptions: Assumptions
    """The modelling choices the run was given -- consumption method, coupon policy."""


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

    as_of: date
    """When the question was **answered**. Decides staleness and nothing else.

    Not the same fact as the question's own ``asked_on``, which is a field of the artefact: the
    verb takes this one so answering an unchanged file next year ages its sources a year.

    On the manifest rather than in the declaration it answers (015 FR-006): a file whose
    horizons moved with the calendar would be a different question every day under one digest,
    so reproducibility is preserved by recording the clock here instead of putting one there.
    """

    regime_id: str
    """Which world the run searched. ``IMPLICIT_REGIME_ID`` where no scenario was in force.

    A result is only reproducible if the world it assumed is recorded, and *every route at once*
    is itself an assumption worth naming.
    """

    projection: ProjectedRun | None
    """The single-projection facts, or ``None`` where the run projected many.

    Four fields that are true of **one** holding over **one** window. An answer has many
    instruments and many horizons and no single holding, and leaving them on the record proper
    would have forced it to invent one (015 research D12).
    """

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
    """Ids of every source behind the reported figures with no verification date, sorted.

    The roll-up of what :attr:`inputs` records per file, taken from the figures' own
    provenance so it describes what the *result* rests on rather than what happened to be
    loaded. Non-empty is the expected state for feature 001 (FR-014, FR-015).

    ⚙ **The real figures are included, and they had to be** (007 FR-013). The nominal figure's
    provenance deliberately excludes the CPI observations -- putting them there would make the
    *nominal* rate appear to rest on a price index it does not -- so a roll-up taken from
    ``hurdle.provenance`` alone would omit every observation behind a real figure. With the
    shipped Ukrainian series that is 411 unverified values behind a reported number, absent
    from the field whose whole job is to name them. A long window therefore makes this list
    long, which is the honest answer rather than a reason to trim it (research.md D6).
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
            unverified_sources=_unverified_ids(_tax_class_provenance(declared)),
        )
        for identifier, declared in declarations.tax_classes.items()
    ]
    funds = [
        InputRef(
            kind="fund",
            id=identifier,
            file=file_name(declarations.fund_files[identifier]),
            version=file_version(declarations.fund_files[identifier]),
            unverified_sources=_unverified_ids(_fund_provenance(declared)),
        )
        for identifier, declared in declarations.funds.items()
    ]
    return tuple(sorted([*instruments, *tax_classes, *funds], key=lambda ref: (ref.kind, ref.id)))


def _fund_provenance(declared: FundDeclaration) -> Provenance:
    """Every source behind one fund declaration, including the ones nothing computes from.

    ⚙ Feature 006. A fund carries more independent observations than a bond does -- its NAV,
    its stated yield, its distribution terms, its spread, both readings of its liquidity,
    each dated cap entry and each recorded fee fact -- and every one of them is a separate
    citation with its own verification date. The union is taken over all of them, including
    the fee facts that are context rather than computed terms: they are still things a
    reader was told, and a manifest that recorded only what the arithmetic touched would
    call a file verified while part of it was not.
    """
    sources = [
        declared.nav_per_unit.provenance,
        declared.declared_yield.provenance,
        declared.spread.provenance,
        declared.liquidity.legal.provenance,
        declared.liquidity.practice.provenance,
        *(fee.provenance for fee in declared.fee_context),
    ]
    terms = declared.distribution
    if terms is not None:
        sources.append(terms.provenance)
        if terms.peg is not None:
            sources.extend(entry.provenance for entry in terms.peg.cap)
    return prov.merge_all(sources)


def _tax_class_provenance(declared: TaxClass) -> Provenance:
    """Every source behind one tax class: the citation of each dated rate entry.

    ⚙ Feature 006 moved the citation from the class to its entries, because two rates
    cited by two sources are two observations. A manifest that recorded only the entry in
    force today would call the class verified while an earlier, still-reachable entry was
    not -- so the union is taken over the whole schedule.
    """
    return prov.merge_all(entry.provenance for entry in declared.rates)


def inflation_input_refs(declarations: InflationDeclarations) -> tuple[InputRef, ...]:
    """Every price series and the declared belief, as manifest input references (007 FR-015).

    A separate function beside :func:`input_refs` rather than more branches inside it,
    mirroring the resolver's own split: the two declaration sets describe different runs, and
    a projection given no CPI is a legitimate run whose manifest simply lists none of these.

    **The assumption is recorded even though it carries no citation.** Its
    ``unverified_sources`` is empty for the owner's own belief -- there is nothing to verify a
    belief against, and an empty list here says exactly that rather than claiming it was
    checked. What the manifest is recording is *which declaration was in force*, which is the
    question FR-015 asks: two runs with two beliefs must be tellable apart afterwards.
    """
    series = [
        InputRef(
            kind="cpi_series",
            id=identifier,
            file=file_name(declarations.series_files[identifier]),
            version=file_version(declarations.series_files[identifier]),
            unverified_sources=_unverified_ids(
                prov.merge_all(item.provenance for item in declared.observations)
            ),
        )
        for identifier, declared in declarations.series.items()
    ]
    assumptions = (
        []
        if declarations.assumption is None or declarations.assumption_file is None
        else [
            InputRef(
                kind="inflation_assumption",
                id=declarations.assumption.id,
                file=file_name(declarations.assumption_file),
                version=file_version(declarations.assumption_file),
                unverified_sources=_unverified_ids(
                    declarations.assumption.provenance
                    if declarations.assumption.provenance is not None
                    else prov.EMPTY
                ),
            )
        ]
    )
    return tuple(sorted([*series, *assumptions], key=lambda ref: (ref.kind, ref.id)))


def official_rate_input_refs(rates: OfficialRateDeclarations) -> tuple[InputRef, ...]:
    """Every declared official-rate series, as manifest input references (018 FR-020).

    A separate function beside :func:`inflation_input_refs` for the same reason that one is
    separate from :func:`input_refs`: the three declaration sets are resolved independently,
    and a run given no rates is a legitimate run whose manifest lists none of these.

    ``unverified_sources`` is the union over **every observation**, because each carries its own
    citation -- one per calendar day since 2019-12-28. That makes the list long, which is the
    honest answer rather than a reason to trim it: nobody has checked any of them.
    """
    return tuple(
        sorted(
            (
                InputRef(
                    kind="official_rate",
                    id=identifier,
                    file=file_name(rates.files[identifier]),
                    version=file_version(rates.files[identifier]),
                    unverified_sources=_unverified_ids(
                        prov.merge_all(item.provenance for item in declared.observations)
                    ),
                )
                for identifier, declared in rates.series.items()
            ),
            key=lambda ref: (ref.kind, ref.id),
        )
    )


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
    as_of: date,
    regime_id: str,
    inflation: InflationDeclarations | None = None,
    official_rates: OfficialRateDeclarations | None = None,
) -> RunManifest:
    """The manifest of one projection: its inputs, their versions, and its digest.

    ⚙ **``inflation`` records which price series and which declared belief were in force**
    (007 FR-015), and ``official_rates`` which series a tax base could have been struck at
    (018 FR-020). Both default to ``None`` because a run given neither is a legitimate run: the
    real-terms slot reports its absence in words, and a base in a currency the tax is already
    assessed in consults no rate at all. The default records nothing rather than recording a
    default.

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
        as_of=as_of,
        regime_id=regime_id,
        projection=ProjectedRun(
            instrument_id=holding.instrument_id,
            holding=holding,
            horizon=horizon,
            assumptions=assumptions,
        ),
        inputs=tuple(
            sorted(
                [
                    *input_refs(declarations),
                    *(() if inflation is None else inflation_input_refs(inflation)),
                    *(() if official_rates is None else official_rate_input_refs(official_rates)),
                ],
                key=lambda ref: (ref.kind, ref.id),
            )
        ),
        seed=seed,
        result_digest=digest_of_projection(result),
        unverified_sources=_unverified_ids(_reported_provenance(result)),
    )


def _reported_provenance(result: Projection) -> Provenance:
    """Every source behind a figure this result reports: the nominal one, and each real one.

    Two sides, unioned, because they are genuinely different source sets and the manifest is
    the one place that answers *"what did this whole result rest on?"*. An unavailable real
    figure contributes nothing -- there is no figure -- which is why the match is over the
    union type rather than an attribute read.
    """
    sources = [result.hurdle.provenance]
    for figure in (result.hurdle.real.realized, result.hurdle.real.assumed):
        if isinstance(figure, RealRate):
            sources.append(figure.provenance)
    return prov.merge_all(sources)


# ---------------------------------------------------------------------------
# 015-the-question: the manifest of a whole answer
# ---------------------------------------------------------------------------


def _ref(
    kind: InputKind,
    identifier: str,
    path: Path,
    sources: Provenance,
    *,
    at_root: bool = False,
) -> InputRef:
    """One input reference, so every family below names its file and version the same way.

    ``at_root`` names a declaration that lives at the data root rather than in a family
    directory. :func:`file_name` keeps the parent so ``instruments/ua.toml`` and ``tax/ua.toml``
    stay distinct -- but a root-level file's parent is *the data root's own directory name*,
    which is one machine's layout, and two checkouts would then describe one declaration two
    ways. That is the exact failure the function exists to prevent, so the parent is dropped.
    """
    return InputRef(
        kind=kind,
        id=identifier,
        file=path.name if at_root else file_name(path),
        version=file_version(path),
        unverified_sources=_unverified_ids(sources),
    )


GROUP_VOCABULARY_ID: Final = "groups"
"""What the group vocabulary is recorded as. It declares no id of its own -- it *is* the set of
them -- and ``InputRef.id`` is documented as a declared id rather than a file name."""


def answer_input_refs(declarations: resolver.AnswerDeclarations) -> tuple[InputRef, ...]:
    """Every file an answer's run read, as input references (015 FR-025, row H3).

    Walked from the loader's own declaration maps rather than by globbing the data root, which
    is what makes SC-008's claim -- *every file the run **read** appears* -- checkable at all: a
    glob would name files nothing consulted and would say nothing about the ones it missed.
    """
    coverage = declarations.candidates.composition.coverage
    ramp = coverage.ramp
    refs = [
        *input_refs(declarations.tuples.instruments),
        *(
            _ref("question", identifier, path, prov.EMPTY)
            for identifier, path in declarations.question_files.items()
        ),
        *(
            _ref(
                "access",
                identifier,
                declarations.tuples.access_files[identifier],
                _access_prov(entry),
            )
            for identifier, entry in declarations.tuples.access.items()
        ),
        *(
            _ref("route", identifier, ramp.route_files[identifier], _route_prov(route))
            for identifier, route in ramp.routes.items()
        ),
        *(
            _ref("stream", identifier, ramp.stream_files[identifier], stream.amount.provenance)
            for identifier, stream in ramp.streams.items()
        ),
        *(
            _ref("channel", identifier, ramp.channel_files[identifier], channel.provenance)
            for identifier, channel in ramp.channels.items()
        ),
        *(
            _ref("venue", identifier, path, prov.EMPTY, at_root=True)
            for identifier, path in ramp.venue_files.items()
        ),
        *(
            _ref("observation_kind", identifier, path, prov.EMPTY, at_root=True)
            for identifier, path in ramp.kind_files.items()
        ),
        *(
            _ref("scenario", identifier, path, prov.EMPTY)
            for identifier, path in ramp.scenario_files.items()
        ),
        _ref(
            "group_vocabulary",
            GROUP_VOCABULARY_ID,
            declarations.tuples.instruments.groups_file,
            prov.EMPTY,
            at_root=True,
        ),
        _ref(
            "composition",
            declarations.candidates.composition.composition_file.stem,
            declarations.candidates.composition.composition_file,
            prov.EMPTY,
        ),
        _ref(
            "candidate_ceiling",
            declarations.candidates.candidates_file.stem,
            declarations.candidates.candidates_file,
            prov.EMPTY,
        ),
        _ref(
            "spendable",
            coverage.spendable_file.stem,
            coverage.spendable_file,
            prov.EMPTY,
        ),
        _ref(
            "early_exit_assumption",
            declarations.tuples.registries.spread_holds.id,
            declarations.tuples.early_exit_file,
            prov.EMPTY,
        ),
    ]
    return tuple(sorted(refs, key=lambda ref: (ref.kind, ref.id)))


def _access_prov(entry: InstrumentAccess) -> Provenance:
    """Both quotes an access entry may carry: what a unit costs, and what it sells for."""
    return prov.merge_all(
        quote.price.provenance for quote in (entry.quote, entry.resale_price) if quote is not None
    )


def _route_prov(route: Route) -> Provenance:
    """Every fee, premium and window a route's legs declare."""
    return prov.merge_all(leg.provenance for leg in route.legs)


def _digest_of(result: Answer | None, refusal: Refused | None) -> str:
    """The digest of whatever the run produced: an answer, or the refusal that replaced it."""
    if result is not None:
        return digest_of_answer(result)
    if refusal is None:
        return digest(("refused",))
    return digest(
        (
            "refused",
            type(refusal).__name__,
            tuple(str(getattr(refusal, name)) for name in getattr(type(refusal), "__slots__", ())),
        )
    )


def digest_of_answer(result: Answer) -> str:
    """The digest of a whole answer: every section, every figure, every stated exclusion.

    A function of the canonical form alone, so provenance -- which the canonical form omits by
    design -- cannot move it. Two runs of one question over one registry agree bit for bit.
    """
    return digest(canonical.of_answer(result))


def of_answer(
    *,
    declarations: resolver.AnswerDeclarations,
    question: Question,
    as_of: date,
    result: Answer | None,
    refusal: Refused | None = None,
) -> RunManifest:
    """The manifest of one answered question: its inputs, their versions, and its digest.

    ``projection`` is ``None``: an answer holds many instruments over many horizons and no
    single holding, and inventing one to fill the field would be a false record rather than an
    incomplete one.

    ``result`` is ``None`` where the question itself refused, and ``refusal`` is what it refused
    with. The digest is then over that refusal's kind and its fields: a constant would give
    every refused run one identity, so two different questions failing two different ways would
    be reported as the same result.
    """
    return RunManifest(
        code_version=terezy.__version__,
        encoding=ENCODING,
        owner_id=question.owner_id,
        as_of=as_of,
        regime_id=question.regime_id,
        projection=None,
        inputs=answer_input_refs(declarations),
        seed=None,
        result_digest=_digest_of(result, refusal),
        unverified_sources=_unverified_ids(prov.EMPTY if result is None else result.provenance),
    )
