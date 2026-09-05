"""Two runs of one request produce the same bytes, in different processes.

Within one process a `frozenset` iterates stably, so a check run twice in one session passes
while the property fails -- the bodies diverge only between runs, on a colleague's machine or
after a restart. The subprocesses below differ in `PYTHONHASHSEED`, which is the only way to
see it (020 FR-019, SC-009).

The OpenAPI document is read here too. It is generated rather than checked in, so nothing else
would catch a schema whose member order follows a set's iteration: a build that regenerated the
client's types would emit a different file on every machine and the diff would name no cause
(020 FR-039).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROGRAM = """
import sys
from pathlib import Path
sys.path.insert(0, "src")
from tests.http_client import served
from terezy.api.http import document

client = served(Path("data"))
for path in ("/venues", "/tax-classes", "/calendars", "/registry", "/openapi.json"):
    response = client.get(f"{document.PREFIX}{path}", params={"as_of": "2026-09-03"})
    sys.stdout.write(response.text)
"""


def _body_under(seed: str) -> str:
    return subprocess.run(
        [sys.executable, "-c", PROGRAM],
        cwd=REPO_ROOT,
        env={**os.environ, "PYTHONHASHSEED": seed},
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def test_two_processes_with_different_hash_seeds_agree() -> None:
    assert _body_under("0") == _body_under("1")
