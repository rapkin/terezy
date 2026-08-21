"""``DeclarationError``: what a broken data file raises, and the only thing it raises.

FR-016: *loading a data file MUST fail loudly on a malformed value, an unrecognised
field, a missing required field, a duplicate identifier, or a reference to an undeclared
tax class -- **naming both the file and the offending field**. A default value MUST NOT
be substituted for anything absent.*

Four fields, because four are what FR-016 asks for and one more would be a field nobody
fills in:

* ``file`` -- which file. Half of FR-016, and the half a ``pydantic.ValidationError``
  structurally cannot carry: it validates a *document*, and by then the path is gone.
* ``field_path`` -- where in the file, dotted, in the notation the file itself uses:
  ``instrument.terms.coupon_rate_pct``. A reader searches for that string and finds the
  line.
* ``problem`` -- what was wrong, in plain language, quoting the offending value.
* ``remedy`` -- what to write instead, **where that is knowable**. Typed
  ``str | None`` and required as an argument: a caller must decide, per raise site,
  whether it knows the fix. A default of ``None`` here would make "no remedy" the thing
  that happens when nobody thought about it, which is the same shape of mistake as a
  defaulted data field.

**Why this is an exception and not a tagged-union member.** The constitution reserves
``raise`` for programmer errors and requires domain *outcomes* to be typed values
(D-E), and a malformed declaration is neither an outcome nor arithmetic: nothing
downstream can proceed, there is no partial answer to return, and every caller's only
sensible response is to stop and report. Principle II says data files *"fail loudly at
load time"*, and the two exceptions already in the core -- ``CurrencyMismatchError`` and
``LedgerInvariantError`` -- set the precedent: an exception is for a statement about the
inputs or the code being wrong, never about the money. ``data-model.md`` lists this type
in its failure table alongside the union members; it is listed there because it carries
its reason in the same structured way, not because it flows through a ``match``.

The structure survives the raise. ``except DeclarationError as exc`` gives back
``exc.file`` and ``exc.field_path`` as data, so the API layer can render them for a UI
without parsing a message -- which is the property a bare ``ValueError`` would lose.

**No ``pydantic`` type crosses this boundary.** The loader adapts ``ValidationError``
into this record; see :mod:`terezy.data.declarations.loader`.
"""

from __future__ import annotations

from pathlib import Path

REMEDY_PREFIX = "To fix it: "
"""How a remedy is introduced in the rendered message. One place, so it reads the same
everywhere and a test can assert on the rendering without pinning whole sentences."""


def render(file: Path, field_path: str, problem: str, remedy: str | None) -> str:
    """The one-line human rendering, as a free function so it can be reused and tested.

    Shaped like a compiler diagnostic -- ``file: [field] problem`` -- because that is the
    form a person maintaining a rate schedule by hand can act on without reading code,
    and because it matches what ``scripts/check_provenance.py`` already prints over the
    same files.
    """
    where = f"{file}: [{field_path}]" if field_path else f"{file}:"
    tail = f" {REMEDY_PREFIX}{remedy}" if remedy else ""
    return f"{where} {problem}{tail}"


class DeclarationError(Exception):
    """A declaration file could not be loaded, and this says which file and which field.

    Carries the four fields as attributes so a caller can act on them structurally, and
    renders them into the message so a caller that only prints the exception still sees
    everything. Inheriting from ``Exception`` is the only inheritance in this package and
    is unavoidable -- ``raise`` requires it.
    """

    file: Path
    """The file that could not be loaded. Absolute or relative exactly as it was given
    to the loader, never rewritten: a reader needs the path they can open."""

    field_path: str
    """Dotted path to the offending field, in the file's own notation. Empty only for a
    problem that belongs to the whole file, such as unparseable TOML."""

    problem: str
    """What was wrong, in plain language, quoting the offending value where there is one."""

    remedy: str | None
    """What to write instead, or ``None`` where the loader genuinely cannot know."""

    def __init__(self, file: Path, field_path: str, problem: str, remedy: str | None) -> None:
        self.file = file
        self.field_path = field_path
        self.problem = problem
        self.remedy = remedy
        super().__init__(render(file, field_path, problem, remedy))
