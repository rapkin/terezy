"""A malformed declaration reaches an HTTP caller naming the file and the field.

Row H2, reinforced at a new surface rather than re-derived: the loader path is unchanged and
`DeclarationError`'s four fields are carried verbatim. It is an error status rather than a typed
refusal in a 200 body, which is the distinction the CLI keeps between `LOAD_FAILED` and
`REFUSED`: nothing was answered and there is no partial result to return.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from terezy.api.http import document
from tests.data_roots import SHIPPED
from tests.http_client import served

DATA_ROOT = SHIPPED
AS_OF = {"as_of": "2026-09-03"}


@pytest.mark.contract
def test_a_malformed_declaration_names_its_file_and_field(tmp_path: Path) -> None:
    scratch = tmp_path / "data"
    shutil.copytree(DATA_ROOT, scratch)
    broken = scratch / "venues.toml"
    broken.write_text(broken.read_text(encoding="utf-8") + "\nnot toml at all [[[\n", "utf-8")

    response = served(scratch).get(f"{document.PREFIX}/venues", params=AS_OF)
    assert response.status_code == 500
    body = response.json()
    assert body["tag"] == "envelopes.DeclarationFailed"
    assert body["file"].endswith("venues.toml")
    assert body["problem"]


@pytest.mark.contract
def test_no_category_returns_partial_data_when_the_root_is_broken(tmp_path: Path) -> None:
    scratch = tmp_path / "data"
    shutil.copytree(DATA_ROOT, scratch)
    (scratch / "venues.toml").write_text("[[venue]]\nid = 1\n", encoding="utf-8")

    client = served(scratch)
    for path in ("/venues", "/routes", "/channels"):
        response = client.get(f"{document.PREFIX}{path}", params=AS_OF)
        assert response.status_code == 500, path
        assert response.json()["tag"] == "envelopes.DeclarationFailed"
