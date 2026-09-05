"""Which directories under ``data/`` need a citation, and the reason where one does not.

Lives in the package rather than in ``scripts/check_provenance.py`` because two readers need
it: the gate, which fails a build over it, and the HTTP layer, which serves an exemption **with
its reason** so that an exempt directory is distinguishable from a citation nobody wrote. The
gate imports these names; there is no second copy to drift.

Together the two lists are exhaustive over ``data/``: a directory in neither is an error rather
than a blind spot, which is what makes the gate fail-closed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

SOURCED_DIRS: Final[tuple[str, ...]] = (
    "tax",
    "instruments",
    "routes",
    "channels",
    "cpi",
    "access",
    "observations",
    "official_rates",
    "calendars",
)
"""Directories whose observed values -- numbers and dates -- must carry a citation.

A subdirectory of one needs no entry of its own: the gate's walk is recursive.

Two entries look surprising and are deliberate. Most of an ``access`` entry is references that
cite nothing, and its one observed value is the price of a unit at the venue -- a market quote,
which is exactly the figure that gets believed without checking and the number every purchase
in a comparison is sized by. A ``calendars`` row holds no number at all and is reached only
because the gate's predicate counts dates: an uncited holiday is a legal value from memory,
and this is the one gate that would otherwise be believed to catch it.
"""

EXEMPT_DIRS: Final[dict[str, str]] = {
    "scenarios": (
        "the owner's own stated beliefs -- regimes, transitions, event probabilities. An "
        "assumption needs a label and a visible consequence, not a source (data/README.md)"
    ),
    "objectives": (
        "the owner's own objective and constraint sets -- stated preferences, not observations "
        "(data/README.md)"
    ),
    "strategies": (
        "the owner's own named allocations -- decisions, not observations. A strategy file that "
        "ever carries a market observation must move that value into a sourced directory rather "
        "than widen this exemption"
    ),
    "streams": (
        "an owner's own salary is a statement of fact by the only person who can make it: an "
        "amount, a cadence, the venues it lands at and is credited to, and which taxation scheme "
        "he is in. Feature 012 removed the one thing here the exemption never covered -- a tax "
        "RATE, which is a public legal fact about the Republic rather than a statement about him. "
        "The rates of every scheme now live in data/tax/schemes/, where a citation is required "
        "(data/README.md)"
    ),
    "composition": (
        "the owner's own policy on how far a search may run -- how many declared routes may be "
        "chained into one candidate. Nothing here describes the world, so there is nothing for a "
        "source to vouch for: it is the same exemption `objectives` and `strategies` carry, and "
        "for the same reason. Every *number* that describes a corridor lives on a leg, in "
        "data/routes/, cited (004 research.md D8)"
    ),
    "questions": (
        "the owner's own questions -- an amount, some subjects, some horizons and a run plan per "
        "subject. A question is one person's stated preference, not an observation about the "
        "world, so there is nothing for a source to vouch for: the same exemption `objectives`, "
        "`strategies`, `composition` and `candidates` carry. If a number describing the world "
        "ever has to live in a question it moves to a sourced directory rather than this "
        "exemption widening (015 FR-003)"
    ),
    "candidates": (
        "the owner's own policy on how many options a search may enumerate before it refuses -- a "
        "single integer, and nothing here describes the world. It is the same exemption "
        "`composition` carries and for the same reason: how far and how wide this person will let "
        "a search run is a fact about him. Every *number* that describes a corridor lives on a "
        "leg, in data/routes/, cited (014 research.md D9)"
    ),
    "spendable": (
        "the owner's own statement of where he spends -- a venue id and a currency code, and "
        "nothing a source could vouch for. It is the same exemption `streams` has and for the "
        "same reason: where a person's money counts as having come back out is a fact about his "
        "life rather than an observation of the world. Every *number* attached to a venue lives "
        "on a leg, in data/routes/, cited (003 research.md D4)"
    ),
    "user": (
        "gitignored per-user data -- what a *run produces* rather than what a person declares: "
        "results, caches, scratch output. Never curated, never committed, and outside this gate "
        "by the Principle VII boundary. The owner's own declarations are committed and live in "
        "the per-owner directories above (008 research.md D2)"
    ),
    "seeds": (
        "the owner's own opening lots -- what he already holds, what he paid, and whether he "
        "knows the price or is stating it from memory. What a person paid for a lot is his own "
        "record rather than an observation of the world, so there is nothing for a source to "
        "vouch for: the same exemption `objectives`, `strategies`, `streams` and `spendable` "
        'carry. A cost he is unsure of is not uncited, it is *marked* -- `basis = "estimated"` '
        "puts a propagating mark on the gain and on the tax charged on it, which is the honest "
        "answer where a citation is not available to anybody (008 research.md D2). If a market "
        "*value* ever has to live here it moves to a sourced directory rather than this exemption "
        "widening to cover it"
    ),
    "goals": (
        "the owner's own targets -- a sum, a date, a contribution. A target is a decision, not an "
        "observation, so there is nothing for a source to vouch for: the same exemption "
        "`objectives` and `strategies` carry, and for the same reason. The growth assumption a "
        "goal is evaluated against is deliberately *not* declared here (008 FR-012); it is an "
        "input carrying its own provenance, so no rate this gate would want to check ever lands "
        "in this directory"
    ),
}
"""Directories exempt from the citation requirement, each BY NAME and WITH ITS REASON."""

KINDS_FILE: Final[str] = "observation_kinds.toml"

KINDS_FILE_EXEMPTION: Final[str] = (
    "the staleness thresholds themselves, which the gate validates as a vocabulary rather than "
    "citing: every other file's `kind` is checked against this one, so a citation here would be "
    "the list vouching for itself"
)
"""Why the one root file the gate excludes from its citation scan is excluded."""


@dataclass(frozen=True, slots=True)
class CitationsRequired:
    """This path's observed values must carry a citation."""

    path: str


@dataclass(frozen=True, slots=True)
class CitationsExempt:
    """This path is exempt, and this is the recorded reason."""

    path: str
    reason: str


def verdict_for(path: str) -> CitationsRequired | CitationsExempt:
    """The gate's verdict for one path under ``data/``, directory or root file.

    The exempt top segment is consulted **before** the file-suffix rule: a ``.toml`` nested
    under an exempt directory is exempt like everything else there, and answering *required*
    for it would make this module disagree with the gate that imports it -- which is the one
    thing it exists to prevent. A root ``.toml`` is scanned like a sourced file, with
    :data:`KINDS_FILE` the single exclusion.
    """
    if path == KINDS_FILE:
        return CitationsExempt(path=path, reason=KINDS_FILE_EXEMPTION)
    top = path.split("/", 1)[0]
    exemption = EXEMPT_DIRS.get(top)
    if exemption is not None:
        return CitationsExempt(path=path, reason=exemption)
    if path.endswith(".toml") or top in SOURCED_DIRS:
        return CitationsRequired(path=path)
    raise ValueError(
        f"{path!r} is in neither SOURCED_DIRS nor EXEMPT_DIRS. Answering `required` for an "
        "unlisted directory would be the silent default that makes a fail-closed gate "
        "fail-open; name it in one of the two lists, with its reason if it is exempt."
    )
