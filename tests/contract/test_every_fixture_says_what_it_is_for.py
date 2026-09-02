"""Every invented declaration names the mechanism it is the only example of.

The owner's rule of 2026-09-02 moved the invented instruments out of the shipped registry and
**kept every one of them**, because each is the sole example of something live: retiring one
deletes the only reachable case of a mechanism, and the deletion looks like tidying. The
defence is that the mechanism has to be written down beside the file -- and a prose list of a
directory is false the moment the directory moves, so it is a check.

``tests/fixtures/data/README.md`` is the list. This asserts the two directions: every file it
names exists, and every file that exists is named.
"""

from __future__ import annotations

import pytest

from tests import data_roots

pytestmark = pytest.mark.contract

README = data_roots.FIXTURES / "README.md"


def _declared_files() -> set[str]:
    """Every fixture declaration under the overlay, as a path relative to it."""
    return {
        str(path.relative_to(data_roots.FIXTURES)) for path in data_roots.FIXTURES.rglob("*.toml")
    }


def test_the_readme_names_every_invented_declaration_and_no_other() -> None:
    prose = README.read_text(encoding="utf-8")
    named = {name for name in _declared_files() if f"`{name}`" in prose}
    assert named == _declared_files(), (
        "a fixture with no line in tests/fixtures/data/README.md is a file nobody can tell "
        "apart from spare data, and the next person to tidy the tree deletes the only example "
        f"of a mechanism. Unnamed: {sorted(_declared_files() - named)}"
    )
