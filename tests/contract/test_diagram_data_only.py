"""A corridor added as data appears in the picture, with no line of source changed.

**SC-002** and **FR-003** -- constitution Principle II applied to *presentation*. A compliance
test for the constitution; it may not be skipped or deleted without an amendment.

Feature 001 made this claim about instruments and proved it three ways in
``tests/contract/test_data_only_extensibility.py``. The same three ways are what make it a
claim here rather than a hope:

1. **A new provider, venue and corridor written to a scratch data root, never seen by this
   repository, appear in the regenerated diagram** -- correctly connected, correctly marked,
   and with nothing in ``src`` touched.
2. **No module in the renderer names a venue, a provider, a route, a corridor or a channel.**
   A branch on a declared id is the Principle II violation the whole design exists to prevent,
   and it is greppable, so it is grepped -- with prose stripped first, because half the
   docstrings in this package cite a specification section and one of them names a corridor to
   explain the rule.
3. **The renderer takes no registry of its own.** Nothing is registered, no decorator runs at
   import, and the diagram has no existence apart from the declarations it is handed.

The scan is proved able to fail, because a scan that cannot fail protects nothing.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

from terezy.api.diagrams import Diagram, Mode, render_graph
from terezy.api.diagrams import marks as diagram_marks
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives.currency import Currency
from terezy.data.declarations import resolver
from tests import diagram_registries as fixture
from tests import source_scan

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = REPO_ROOT / "data"
DIAGRAMS_ROOT = REPO_ROOT / "src" / "terezy" / "api" / "diagrams"

NEW_VENUE = "wise_eur_fixture"
NEW_ROUTE = "monobank_to_wise_fixture"
NEW_EXIT = "wise_to_monobank_fixture"
NEW_PROVIDER = "A Provider This Repository Has Never Seen"

DECLARED_NAMES = re.compile(
    # venues; channels and providers; streams and scenarios
    r"monobank|binance|coinbase|ibkr|inzhur|wise"
    r"|\bp2p\b|nbu|interbank"
    r"|salary|contract_usd|wartime|normalized|war_end",
    re.IGNORECASE,
)
"""Every declared name a renderer might be tempted to branch on. None may appear in the
package's *behaviour*."""


def _scratch_data_root(tmp_path: Path) -> Path:
    """A copy of ``data/`` with one new venue, one new corridor and its exit, added as files.

    Copied rather than mutated in place, and extended rather than replaced, so the addition is
    exactly what a person adding a corridor would do: one venue line, two route files. Nothing
    else changes, in ``src`` least of all.
    """
    root = tmp_path / "data"
    shutil.copytree(DATA_ROOT, root)

    (root / "venues.toml").write_text(
        (root / "venues.toml").read_text(encoding="utf-8")
        + f'''
[[venue]]
id         = "{NEW_VENUE}"
name       = "A venue added purely as data (SYNTHETIC FIXTURE)"
currencies = ["UAH", "USD"]
''',
        encoding="utf-8",
    )

    for route_id, origin, destination, partner, direction in (
        (NEW_ROUTE, "monobank_uah", NEW_VENUE, NEW_EXIT, "inbound"),
        (NEW_EXIT, NEW_VENUE, "monobank_uah", None, "exit"),
    ):
        # Omitted entirely on the exit route: a pairing is declared once, by the inbound
        # half (feature 002's FR-027), and the loader refuses an exit route that names one.
        partner_line = "" if partner is None else f'partner_route = "{partner}"\n'
        (root / "routes" / f"{route_id}.toml").write_text(
            f'''# SYNTHETIC FIXTURE, added by a test as data only.
[route]
id            = "{route_id}"
provider      = "{NEW_PROVIDER}"
origin        = "{origin}"
destination   = "{destination}"
direction     = "{direction}"
{partner_line}status        = "open"

  [[route.leg]]
  index                  = 0
  kind                   = "transfer"
  from_venue             = "{origin}"
  to_venue               = "{destination}"
  from_ccy               = "UAH"
  to_ccy                 = "UAH"
  fee_pct                = 1.25
  fee_fixed              = 7.5
  latency_days           = 1
  disruption_probability = 0.0
  kind_of_observation    = "bank_fee_schedule"
  source                 = "SYNTHETIC FIXTURE -- invented by a contract test. Not a tariff."
  retrieved_on           = "2026-08-20"
  verified_on            = ""
''',
            encoding="utf-8",
        )

    scenario = root / "scenarios" / "war_end.toml"
    scenario.write_text(
        scenario.read_text(encoding="utf-8").replace(
            '    "binance_p2p_to_monobank",\n  ]',
            f'    "binance_p2p_to_monobank",\n    "{NEW_ROUTE}",\n    "{NEW_EXIT}",\n  ]',
            1,
        ),
        encoding="utf-8",
    )
    return root


class TestACorridorAddedAsDataAppearsInThePicture:
    """SC-002 under the loosest possible conditions: files this repository never saw."""

    @staticmethod
    def _rendered(tmp_path: Path) -> Diagram:
        declared = resolver.ramp_from_data_root(
            _scratch_data_root(tmp_path), base_currency=Currency.UAH
        )
        rendered = render_graph(
            venues=declared.venues,
            routes=declared.routes,
            channels=declared.channels,
            regime=fixture.shipped_regime(declared, "war_end", "wartime"),
            mode=Mode.DECLARED_FIGURES,
            kinds=declared.kinds,
            as_of=fixture.AS_OF,
        )
        assert isinstance(rendered, Diagram)
        return rendered

    def test_the_new_venue_the_new_provider_and_both_new_routes_are_drawn(
        self, tmp_path: Path
    ) -> None:
        text = self._rendered(tmp_path).text
        assert f'["venue {NEW_VENUE} · ' in text
        assert f"route {NEW_ROUTE} " in text
        assert f"route {NEW_EXIT} " in text
        assert NEW_PROVIDER in text

    def test_the_new_corridor_is_connected_exactly_as_declared(self, tmp_path: Path) -> None:
        labels = fixture.labels_by_route(self._rendered(tmp_path).text)
        assert "leg 0 transfer" in labels[NEW_ROUTE]
        assert "status: open" in labels[NEW_ROUTE]

    def test_the_new_corridors_declared_figures_are_rendered_through_the_one_rule(
        self, tmp_path: Path
    ) -> None:
        """``fee_pct = 1.25`` in the file is 1.25 **percent**, divided by 100 once at the
        data boundary (``METHODOLOGY`` §9), and rendered back as ``1.25%`` by the one rule."""
        labels = fixture.labels_by_route(self._rendered(tmp_path).text)
        assert "declared fee 1.25% + 7.50 UAH" in labels[NEW_ROUTE]

    def test_the_new_corridor_is_marked_exactly_as_it_declares_itself(self, tmp_path: Path) -> None:
        """Correctly *marked*, not merely present: an empty ``verified_on`` and a citation
        that says SYNTHETIC FIXTURE, so both marks appear and neither is invented."""
        labels = fixture.labels_by_route(self._rendered(tmp_path).text)
        assert diagram_marks.token(Mark.UNVERIFIED) in labels[NEW_ROUTE]
        assert diagram_marks.token(Mark.SYNTHETIC) in labels[NEW_ROUTE]

    def test_the_new_destination_is_comparison_ready_because_its_exit_is_declared(
        self, tmp_path: Path
    ) -> None:
        """The other half of the same claim: adding the *exit* as data removes the mark."""
        text = self._rendered(tmp_path).text
        node = next(line for line in text.splitlines() if f'["venue {NEW_VENUE} ' in line)
        assert diagram_marks.token(Mark.NO_EXIT_DECLARED) not in node

    def test_the_shipped_diagram_does_not_already_contain_it(self, tmp_path: Path) -> None:
        """Otherwise every assertion above would pass without the scratch root."""
        assert NEW_VENUE not in fixture.shipped_declarations().venues
        assert self._rendered(tmp_path).text != _shipped_graph_text()


def _shipped_graph_text() -> str:
    declared = fixture.shipped_declarations()
    rendered = render_graph(
        venues=declared.venues,
        routes=declared.routes,
        channels=declared.channels,
        regime=fixture.shipped_regime(declared, "war_end", "wartime"),
        mode=Mode.DECLARED_FIGURES,
        kinds=declared.kinds,
        as_of=fixture.AS_OF,
    )
    assert isinstance(rendered, Diagram)
    return rendered.text


class TestNoModuleInTheRendererNamesAnythingDeclared:
    """The greppable half of SC-002, and the honest one.

    "Zero lines of source code changed" is a claim about the *renderer*, and the way it fails
    is a branch on a declared id. That is detectable, so it is detected here rather than
    asserted in a commit message.
    """

    def test_no_module_names_a_venue_a_provider_a_corridor_or_a_channel(self) -> None:
        found = {
            path.name: sorted(set(DECLARED_NAMES.findall(source_scan.executable_source(path))))
            for path in sorted(DIAGRAMS_ROOT.rglob("*.py"))
            if DECLARED_NAMES.search(source_scan.executable_source(path))
        }
        assert not found, (
            "a renderer module names something the declarations declare, so that thing's "
            f"appearance in a diagram is code rather than data (Principle II): {found}"
        )

    def test_the_scan_looked_at_the_whole_package(self) -> None:
        assert len({path.name for path in DIAGRAMS_ROOT.rglob("*.py")}) >= 5

    def test_the_scan_would_catch_a_branch_on_a_declared_id(self) -> None:
        """A scan that can never fail protects nothing.

        Also proves the prose stripping keeps real code: a string *compared against* survives,
        while a string that only describes a rule does not.
        """
        assert DECLARED_NAMES.search(
            source_scan.strip_prose(
                '''
"""A docstring mentioning nothing at all."""


def f(route: object) -> bool:
    """Another docstring."""
    return route.id == "monobank_to_binance_p2p"
'''
            )
        )
        assert not DECLARED_NAMES.search(
            source_scan.strip_prose(
                '''
"""A module docstring about the monobank to binance p2p corridor -- prose, not behaviour."""

X: int = 1
"""An attribute docstring naming inzhur and coinbase."""
# A comment about the p2p channel.
'''
            )
        )

    def test_the_renderer_registers_nothing_at_import(self) -> None:
        """No decorator, no subclass scan, no import-time side effect.

        The diagram has no existence apart from the declarations it is handed, which is what
        makes "adding a corridor is a data change" true by construction rather than by habit.
        """
        for path in sorted(DIAGRAMS_ROOT.rglob("*.py")):
            behaviour = source_scan.executable_source(path)
            for smell in ("register", "__init_subclass__", "__subclasses__", "importlib"):
                assert smell not in behaviour, f"{path.name} contains {smell}"
