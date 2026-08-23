"""The marks reach the picture, and they survive it.

**SC-004** and **SC-005**; **FR-004**, **FR-005**, **FR-012** through **FR-015**.

Honesty marks are this project's identity (Principle I), and the picture will travel further
than the tables -- it gets pasted into reports and read by people who never open the TOML. So
a diagram with wrong marks is worse than no diagram.

**The decision this module enforces is research.md D4: marks live in label *text*.** Mermaid
``classDef`` styling may add emphasis on top; it may never be the only carrier. A mark
carried by a colour is lost the moment the text is diffed, re-themed, or read as source in a
golden file -- and golden files are one of exactly two places this output lands (FR-021).
Every end-to-end assertion below therefore **strips every style declaration first** and then
looks for the marks.

The vocabulary half runs first because it is what makes "strip the styling and the marks are
still there" a single testable claim rather than six similar ones.
"""

from __future__ import annotations

import re
from dataclasses import replace
from datetime import date

import pytest

from terezy.api.diagrams import Diagram, Mode, figures, marks, mermaid, render_graph
from terezy.api.diagrams.marks import Mark
from terezy.core.primitives import provenance as prov
from terezy.core.primitives import staleness
from terezy.core.primitives.currency import Currency
from terezy.core.primitives.provenance import Provenance, SourceRef
from terezy.core.primitives.staleness import ObservationKind
from terezy.core.routes.channels import ChannelSide
from terezy.core.scenarios.regimes import Regime
from tests import diagram_registries as fixture

pytestmark = pytest.mark.contract

STYLE_DECLARATION = re.compile(r"^\s*classDef .*$", re.MULTILINE)
STYLE_APPLICATION = re.compile(r":::[A-Za-z_][A-Za-z0-9_]*")


def unstyled(text: str) -> str:
    """The diagram with every style declaration and every class application removed.

    What is left is exactly what a reader sees who has no colours at all: a diff, a
    monochrome terminal, a themed viewer that renders the classes differently. If a mark
    only existed in the styling, it is gone by the time an assertion below runs.
    """
    return STYLE_APPLICATION.sub("", STYLE_DECLARATION.sub("", text))


class TestTheVocabulary:
    """Six marks, pairwise distinct, and the two states that are the absence of one."""

    def test_the_enum_is_closed_and_is_the_six_the_data_model_names(self) -> None:
        assert {mark.name for mark in Mark} == {
            "UNVERIFIED",
            "STALE",
            "SYNTHETIC",
            "CLOSED",
            "NO_EXIT_DECLARED",
            "EXIT_COST_UNKNOWN",
        }

    def test_every_token_is_distinct_from_every_other(self) -> None:
        """FR-015's *pairwise* distinguishable, asserted as a set size rather than by eye."""
        tokens = [marks.token(mark) for mark in Mark]
        assert len(set(tokens)) == len(tokens)

    def test_no_token_is_a_substring_of_another(self) -> None:
        """Substring collision would make ``"STALE" in text`` a lie for some other label.

        Over the **whole** vocabulary, marks and the three named absences together -- which is
        where the collision actually happened: an earlier ``"STALENESS NOT ASSESSED"``
        contained ``STALE``, so a label saying nobody had aged the sources answered yes to
        "is this stale?".
        """
        vocabulary = [marks.token(mark) for mark in Mark] + [
            marks.CLEAN,
            marks.UNSOURCED,
            marks.UNASSESSED,
        ]
        assert len(set(vocabulary)) == len(vocabulary)
        for token in vocabulary:
            others = [other for other in vocabulary if other != token]
            assert not any(token in other for other in others), token

    def test_an_empty_mark_set_is_named_rather_than_left_as_an_empty_space(self) -> None:
        """An empty marks segment is indistinguishable from a renderer that forgot."""
        assert marks.segment(()) == f"marks: {marks.CLEAN}"

    def test_a_figure_resting_on_no_cited_source_says_so_instead(self) -> None:
        """``provenance.EMPTY`` is not unverified -- and it is not verified either.

        Rendering it as clean would claim a verification that never happened, which is the
        laundering ``core.primitives.provenance`` exists to prevent. It gets its own words.
        """
        assert marks.segment((), unsourced=True) == f"marks: {marks.UNSOURCED}"
        assert marks.segment((), unsourced=True) != marks.segment(())

    def test_unverified_and_stale_both_appear_and_neither_swallows_the_other(self) -> None:
        """FR-013: they are different claims -- checked against a source, versus read from
        it too long ago -- and a value can be either without being the other."""
        both = marks.segment((Mark.STALE, Mark.UNVERIFIED))
        assert marks.token(Mark.UNVERIFIED) in both
        assert marks.token(Mark.STALE) in both

    def test_the_segment_order_is_the_enum_order_regardless_of_the_argument_order(
        self,
    ) -> None:
        """Determinism (FR-016) reaches down to this: no ``set`` iteration decides text."""
        assert marks.segment((Mark.STALE, Mark.UNVERIFIED)) == marks.segment(
            (Mark.UNVERIFIED, Mark.STALE)
        )

    def test_a_source_nobody_aged_is_not_reported_as_current(self) -> None:
        """``STALENESS NOT ASSESSED`` is the third absence, and it is not :data:`CLEAN`.

        The same ambiguity ``core.primitives.staleness.UNASSESSED`` exists to remove: a
        verdict that assessed nothing must not wear a clean verdict's tick. A costed path
        reads staleness out of the verdict its result carries, so a source that verdict never
        looked at reaches this branch.
        """
        assert marks.segment((), assessed=False) == f"marks: {marks.UNASSESSED}"
        assert marks.segment((), assessed=False) != marks.segment(())
        assert marks.token(Mark.STALE) not in marks.segment((), assessed=False), (
            "'nobody checked' and 'checked and found stale' are different claims, and a "
            "label that contains the STALE token answers the wrong one"
        )

    def test_an_unsourced_figure_does_not_also_say_its_absent_sources_were_not_aged(
        self,
    ) -> None:
        """Two tokens for one absence would read as two separate problems."""
        both = marks.segment((), unsourced=True, assessed=False)
        assert both == f"marks: {marks.UNSOURCED}"

    def test_no_applicable_mark_means_no_style_class_to_apply(self) -> None:
        """A clean element is not emphasised, because there is nothing to draw the eye to."""
        assert marks.style_class_for(()) is None
        assert marks.style_class_for((Mark.STALE,)) == marks.STYLE_CLASS[Mark.STALE]

    def test_every_mark_has_a_style_class_and_the_classes_are_distinct(self) -> None:
        """Styling is emphasis, and emphasis still has to be unambiguous."""
        classes = [marks.STYLE_CLASS[mark] for mark in Mark]
        assert len(set(classes)) == len(classes)

    def test_a_source_that_declares_itself_synthetic_is_read_as_synthetic(self) -> None:
        """FR-014 surfaces the declaration; it does not invent a detection mechanism.

        Every fixture in this repository says ``SYNTHETIC FIXTURE`` in its citation, in
        those words -- ``data/routes/*.toml``, ``data/venues.toml``,
        ``tests/coverage_registries.py``. That phrase is the declaration, and this is the
        one place it is read.
        """
        synthetic = Provenance(
            frozenset(
                {
                    SourceRef(
                        id="s",
                        citation="SYNTHETIC FIXTURE -- invented, not a real tariff.",
                        retrieved_on=date(2026, 8, 1),
                        verified_on=None,
                    )
                }
            )
        )
        real = Provenance(
            frozenset(
                {
                    SourceRef(
                        id="r",
                        citation="https://bank.gov.ua/some-real-tariff",
                        retrieved_on=date(2026, 8, 1),
                        verified_on=date(2026, 8, 2),
                    )
                }
            )
        )
        assert Mark.SYNTHETIC in marks.epistemic(synthetic, stale=False)
        assert Mark.SYNTHETIC not in marks.epistemic(real, stale=False)
        assert marks.epistemic(real, stale=False) == ()
        assert marks.epistemic(real, stale=True) == (Mark.STALE,)
        assert Mark.UNVERIFIED in marks.epistemic(synthetic, stale=False)


class TestAllSixStatesInOneDiagram:
    """User Story 3's independent test, as one fixture and one render.

    The registry below carries a verified-and-current route, an unverified one, a stale one,
    one that is both, a closed one, and a destination nothing exits -- plus a synthetic
    entry. Every assertion runs against :func:`unstyled`.
    """

    @staticmethod
    def _rendered() -> str:
        return unstyled(fixture.six_state_graph().text)

    def test_every_state_appears_in_the_displayed_text(self) -> None:
        text = self._rendered()
        for mark in Mark:
            if mark is Mark.EXIT_COST_UNKNOWN:
                continue  # a costed-path mark; asserted in test_diagram_refusals.py
            assert marks.token(mark) in text, f"{mark.name} is not in the displayed text"
        assert marks.CLEAN in text, "the verified, current, open route is not distinguishable"

    def test_the_states_are_pairwise_distinguishable_on_their_own_edges(self) -> None:
        """Not merely present somewhere -- present on the element they describe."""
        labels = fixture.labels_by_route(self._rendered())
        assert marks.CLEAN in fixture.marks_in(labels[fixture.VERIFIED_ROUTE])
        assert marks.token(Mark.UNVERIFIED) in fixture.marks_in(labels[fixture.UNVERIFIED_ROUTE])
        assert marks.token(Mark.STALE) in fixture.marks_in(labels[fixture.STALE_ROUTE])
        assert marks.token(Mark.UNVERIFIED) in fixture.marks_in(labels[fixture.BOTH_ROUTE])
        assert marks.token(Mark.STALE) in fixture.marks_in(labels[fixture.BOTH_ROUTE])
        assert marks.token(Mark.CLOSED) in fixture.marks_in(labels[fixture.CLOSED_ROUTE])

    def test_stale_and_unverified_are_not_the_same_mark_on_the_same_edge(self) -> None:
        labels = fixture.labels_by_route(self._rendered())
        assert marks.token(Mark.STALE) not in fixture.marks_in(labels[fixture.UNVERIFIED_ROUTE])
        assert marks.token(Mark.UNVERIFIED) not in fixture.marks_in(labels[fixture.STALE_ROUTE])

    def test_a_closed_route_is_present_marked_and_distinct_from_an_open_one(self) -> None:
        """FR-004: closed and nonexistent are different facts and must look different."""
        labels = fixture.labels_by_route(self._rendered())
        assert fixture.CLOSED_ROUTE in labels, "a closed route was omitted rather than marked"
        assert marks.token(Mark.CLOSED) not in fixture.marks_in(labels[fixture.VERIFIED_ROUTE])
        assert "status: closed" in labels[fixture.CLOSED_ROUTE]
        assert "status: open" in labels[fixture.VERIFIED_ROUTE]

    def test_a_route_that_does_not_exist_appears_nowhere(self) -> None:
        assert "no_such_route" not in self._rendered()

    def test_the_marks_are_not_carried_by_styling_alone(self) -> None:
        """The point of the whole module: strip the colours, the marks are still words.

        Proved from both sides -- the styling really is present in the raw text, so the
        stripping above really did remove something.
        """
        raw = fixture.six_state_graph().text
        assert "classDef " in raw, "no styling was emitted, so stripping it proves nothing"
        assert STYLE_APPLICATION.search(raw), "no class was applied to any element"
        assert "classDef " not in self._rendered()
        assert marks.token(Mark.UNVERIFIED) in self._rendered()

    def test_a_synthetic_fixture_can_never_pass_as_the_owners_real_options(self) -> None:
        """FR-014, and it is on the caption so it cannot be missed by reading one edge."""
        assert marks.token(Mark.SYNTHETIC) in self._rendered().splitlines()[1]


class TestTheUnverifiedMarkPropagatesToEveryElement:
    """**SC-005**: one unverified input, and 100% of what depicts it is marked.

    The same propagation ``core.primitives.provenance`` guarantees for numbers, asserted for
    the picture. Not sampled: every edge derived from the unverified leg is checked.
    """

    def test_every_element_depicting_the_unverified_input_carries_the_mark(self) -> None:
        text = unstyled(fixture.one_unverified_graph().text)
        labels = fixture.labels_by_route(text)
        derived = [label for route_id, label in labels.items() if route_id in fixture.DERIVED_FROM]
        assert derived, "the fixture drew nothing, so 100% of nothing is not the claim"
        assert all(marks.token(Mark.UNVERIFIED) in fixture.marks_in(label) for label in derived)

    def test_the_route_that_does_not_rest_on_it_is_not_marked(self) -> None:
        """A mark that appears everywhere carries no information."""
        labels = fixture.labels_by_route(unstyled(fixture.one_unverified_graph().text))
        assert marks.token(Mark.UNVERIFIED) not in fixture.marks_in(labels[fixture.VERIFIED_ROUTE])


class TestTheChannelPremiumCarriesItsOwnMarks:
    """FR-012, FR-013 through the quote, not only through the leg.

    A channel side is **its own observation**: its own source, its own verification date, its
    own ``kind`` and therefore its own staleness threshold. On the §4.3.1 corridor every
    declared fee is zero and the premium is the whole cost, so an edge marked from its leg
    alone would report the most decision-relevant stale figure in the registry as current.
    """

    def test_a_stale_premium_on_a_fresh_fee_leg_does_not_render_clean(self) -> None:
        text = unstyled(fixture.graph_of(fixture.stale_premium_registry()).text)
        label = fixture.labels_by_route(text)[fixture.STALE_PREMIUM_ROUTE]
        assert marks.token(Mark.STALE) in fixture.marks_in(label), (
            "the leg's own fee schedule is fresh and verified; the premium it applies was "
            "last seen years ago, and the edge showing that premium must say so"
        )
        assert marks.CLEAN not in fixture.marks_in(label)

    def test_the_fee_schedule_behind_that_leg_really_is_fresh_and_verified(self) -> None:
        """Otherwise the test above would pass for the wrong reason."""
        registry = fixture.stale_premium_registry()
        leg = registry.routes[fixture.STALE_PREMIUM_ROUTE].legs[0]
        verdict = staleness.staleness_of(
            leg.provenance, registry.kinds, kind=leg.kind_of_observation, as_of=fixture.AS_OF
        )
        assert not staleness.any_stale(verdict)
        assert not prov.is_unverified(leg.provenance)

    def test_the_rendered_edge_is_stale_under_the_sides_kind_and_not_the_channels(self) -> None:
        """**M2.** The three-table ageing, pinned on the *rendered text*.

        The premium is :data:`EIGHTY_TWO_DAYS_AGO` old: stale under ``p2p_premium``'s 7 days,
        current under ``bank_fee_schedule``'s 365. So this edge renders ``STALE`` only if the
        renderer ages the side under **the side's own** declared kind. Collapse the three
        declared kinds into one -- ``staleness_of(channel.provenance, kind=channel.kind)``,
        which is exactly the defect ``cost._channel_verdicts`` was written to fix -- and the
        premium ages under 365 days, comes back current, and this edge renders clean.

        The earlier version of this test asserted only fixture properties (``staleness_days``,
        ``side.kind``) and never looked at a diagram, so the collapse passed it. This one reads
        the label.
        """
        label = fixture.labels_by_route(
            unstyled(fixture.graph_of(fixture.stale_premium_registry()).text)
        )[fixture.STALE_PREMIUM_ROUTE]
        assert marks.token(Mark.STALE) in fixture.marks_in(label)
        assert marks.CLEAN not in fixture.marks_in(label)

    def test_the_discriminating_age_really_discriminates(self) -> None:
        """Otherwise the test above passes under the collapsed implementation too.

        82 days has to fall **between** the two declared thresholds. If someone retunes
        ``p2p_premium`` past 82 days, or ``bank_fee_schedule`` below it, the test above stops
        distinguishing the two implementations and this one says so.
        """
        registry = fixture.stale_premium_registry()
        age = (fixture.AS_OF - fixture.EIGHTY_TWO_DAYS_AGO).days
        assert age == 82
        assert registry.kinds[fixture.FAST_KIND].staleness_days < age
        assert age < registry.kinds[fixture.SLOW_KIND].staleness_days

    def test_the_side_and_the_channel_declare_different_kinds_in_the_fixture(self) -> None:
        """And the two kinds have to differ, or there is nothing to collapse."""
        registry = fixture.stale_premium_registry()
        quote = registry.channels["p2p"]
        assert quote.buy_side.kind == fixture.FAST_KIND
        assert quote.kind == fixture.SLOW_KIND
        assert registry.routes[fixture.STALE_PREMIUM_ROUTE].legs[0].kind_of_observation == (
            fixture.SLOW_KIND
        )

    def test_the_reference_rates_own_sources_are_what_remain_of_the_union(self) -> None:
        """``_reference_sources`` is a set difference, and returning the union instead passes
        every other test in this file.

        A channel's ``provenance`` is the reference's sources **and** both sides'. Ageing that
        whole union under the channel's kind is the same collapse by another route, so the
        split is asserted directly: the reference's own sources are the ones no side cites.
        """
        quote = fixture.stale_premium_registry().channels["p2p"]
        reference = figures._reference_sources(quote)
        side_ids = {ref.id for ref in quote.buy_side.provenance.sources} | {
            ref.id for ref in quote.sell_side.provenance.sources
        }
        assert {ref.id for ref in reference.sources} == {"p2p:reference"}
        assert not {ref.id for ref in reference.sources} & side_ids
        assert reference.sources < quote.provenance.sources

    def test_a_leg_naming_an_undeclared_channel_fails_loudly(self) -> None:
        """There is no default channel, and a diagram may not invent one.

        Substituting "the official rate" for a misspelt id would reprice a P2P leg at the
        reference and delete the entire spread this project exists to measure -- and here it
        would do it in a picture, where nothing else would contradict it.
        """
        registry = fixture.stale_premium_registry()
        with pytest.raises(KeyError, match="p2p"):
            render_graph(
                venues=registry.venues,
                routes=registry.routes,
                channels={},
                regime=registry.regime,
                mode=Mode.DECLARED_FIGURES,
                kinds=registry.kinds,
                as_of=fixture.AS_OF,
            )

    def test_a_side_declaring_neither_form_is_refused_rather_than_drawn_as_free(self) -> None:
        """FR-010 has no third form, and "no premium" is not one of the two.

        "At the reference" is declarable as a zero premium, so an absence can only be an
        unfinished declaration — and rendering it as nothing would draw the corridor at the
        reference, the cheapest it could possibly be. The loader refuses such a file; reaching
        the renderer with one means that check was bypassed, so it raises naming the channel.
        """
        registry = fixture.stale_premium_registry()
        quote = registry.channels["p2p"]
        empty = ChannelSide(
            markup_bps=None,
            premium_per_unit=None,
            kind=fixture.FAST_KIND,
            provenance=quote.buy_side.provenance,
        )
        with pytest.raises(ValueError, match="p2p"):
            render_graph(
                venues=registry.venues,
                routes=registry.routes,
                channels={"p2p": replace(quote, buy_side=empty)},
                regime=registry.regime,
                mode=Mode.DECLARED_FIGURES,
                kinds=registry.kinds,
                as_of=fixture.AS_OF,
            )


class TestNoDeclaredStringCanForgeAMark:
    """**F1.** Escaping the separator closed one route to a forged mark. There were three.

    A label is a sequence of fields, and a mark is a field. So a declaration forges a mark if it
    can *add* a field -- which the separator allowed -- **or** if it can *be* one, which two
    fields allowed by being bare, unprefixed declared text: a venue's name and a route's
    provider. Neither needed a separator. A route whose declared provider is
    ``marks: VERIFIED AND CURRENT`` put those exact characters into a label whose real marks
    field said ``UNVERIFIED + CLOSED``.

    Both routes are closed now, and by different mechanisms, because they are different
    failures. Every field carrying declared text begins with a renderer-owned word
    (``name ``, ``provider ``), so no declaration can *be* a field; and
    ``mermaid.MARKS_FIELD`` is reserved out of declared text, so no declaration can *contain*
    the token either. The first protects a reader looking at the picture, the second protects
    everything that parses the text -- a diff, a golden file, and the assertions in this suite.
    """

    @staticmethod
    def _label() -> str:
        text = unstyled(fixture.graph_of(fixture.forged_registry()).text)
        return fixture.labels_by_route(text)[fixture.FORGED_ROUTE]

    def test_the_forged_provider_does_not_read_as_a_clean_mark(self) -> None:
        """The reviewer's own demonstration, in the assertion shape this suite uses."""
        label = self._label()
        assert marks.CLEAN not in fixture.marks_in(label), (
            "a declared provider is reading as the renderer's own clean mark, on a route that "
            f"is actually unverified and closed: {label}"
        )

    def test_the_forged_venue_name_does_not_read_as_a_clean_mark(self) -> None:
        text = unstyled(fixture.graph_of(fixture.forged_registry()).text)
        node = next(line for line in text.splitlines() if fixture.FORGED_VENUE in line)
        assert "marks: " not in node, (
            "a venue node with no mark of its own must not acquire one from its declared name: "
            f"{node}"
        )

    def test_the_label_carries_exactly_one_marks_field_and_it_is_the_real_one(self) -> None:
        """Read by position in the grammar rather than by substring -- the stronger form."""
        assert fixture.marks_of(self._label()) == marks.segment(
            (Mark.UNVERIFIED, Mark.CLOSED), unsourced=False
        )

    def test_no_field_of_the_label_is_bare_declared_text(self) -> None:
        """The structural half: a declaration can no longer *be* a field.

        Both declared strings are still displayed in full -- nothing is dropped and nothing is
        truncated -- but each sits inside a field the renderer opened and named.
        """
        fields = fixture.fields_of(self._label())
        assert fixture.FORGERY not in fields
        assert any(field.startswith("provider ") for field in fields)
        assert any(fixture.FORGERY.replace(":", "#58;") in field for field in fields), (
            "the declared provider must still be shown in full; escaping is not truncation"
        )

    def test_the_forgery_is_still_the_declared_string_after_decoding(self) -> None:
        """FR-017: escaping may never cost a reader the name that was declared."""
        assert mermaid.escape(fixture.FORGERY).replace("#58;", ":") == fixture.FORGERY

    def test_the_fixture_really_declares_a_forgery_and_a_contradicting_mark(self) -> None:
        """Otherwise every assertion above passes for a reason that is not about forging."""
        registry = fixture.forged_registry()
        assert registry.venues[fixture.FORGED_VENUE].name == fixture.FORGERY
        assert registry.routes[fixture.FORGED_ROUTE].provider == fixture.FORGERY
        assert fixture.FORGERY == marks.PREFIX + marks.CLEAN
        assert registry.routes[fixture.FORGED_ROUTE].status == "closed"


class TestEveryShippedRouteRendersSynthetic:
    """The shipped registry is invented, and the picture of it says so.

    ``SIMULATOR_SPEC.md`` §11 item 1: the owner's real P2P premium, card limit and exchange
    fees have never been observed, and every route file in ``data/routes/`` declares itself
    a synthetic fixture. If someone lands a real, cited corridor, this test goes red -- and
    that is the right moment to look at the diagram again.
    """

    def test_the_wartime_graph_of_the_shipped_data_is_marked_synthetic(self) -> None:
        declared = fixture.shipped_declarations()
        regime = fixture.shipped_regime(declared, "war_end", "wartime")
        rendered = render_graph(
            venues=declared.venues,
            routes=declared.routes,
            channels=declared.channels,
            regime=regime,
            mode=Mode.TOPOLOGY,
            kinds=declared.kinds,
            as_of=date(2026, 8, 21),
        )
        assert isinstance(rendered, Diagram)
        text = unstyled(rendered.text)
        labels = fixture.labels_by_route(text)
        assert set(labels) == set(regime.route_ids)
        assert all(
            marks.token(Mark.SYNTHETIC) in fixture.marks_in(label) for label in labels.values()
        )


class TestTheFixtureIsHonestAboutWhatItProves:
    """A fixture that quietly stopped covering a state would make the suite green and wrong."""

    def test_the_six_state_registry_really_declares_six_different_states(self) -> None:
        registry = fixture.six_state_registry()
        assert len(registry.routes) == 6
        statuses = {route.status for route in registry.routes.values()}
        assert statuses == {"open", "closed"}

    def test_the_stale_route_is_stale_under_its_own_declared_threshold(self) -> None:
        """Not stale by a number invented here: stale under ``data``'s own kind thresholds."""
        registry = fixture.six_state_registry()
        kind = registry.kinds[fixture.FAST_KIND]
        assert isinstance(kind, ObservationKind)
        stale_leg = registry.routes[fixture.STALE_ROUTE].legs[0]
        age = (fixture.AS_OF - next(iter(stale_leg.provenance.sources)).retrieved_on).days
        assert age > kind.staleness_days


class TestTheRegimeAndTheCurrencySafetyOfTheFixture:
    """Guards against the fixture drifting into a shape the loader would refuse."""

    def test_every_fixture_leg_moves_a_currency_its_endpoints_can_hold(self) -> None:
        registry = fixture.six_state_registry()
        for route in registry.routes.values():
            for leg in route.legs:
                assert leg.from_ccy in registry.venues[leg.from_venue].currencies
                assert leg.to_ccy in registry.venues[leg.to_venue].currencies

    def test_the_regime_names_only_declared_routes(self) -> None:
        registry = fixture.six_state_registry()
        assert isinstance(registry.regime, Regime)
        assert registry.regime.route_ids <= set(registry.routes)

    def test_the_fixture_currencies_are_the_declared_enum(self) -> None:
        registry = fixture.six_state_registry()
        for venue in registry.venues.values():
            assert all(isinstance(currency, Currency) for currency in venue.currencies)
            assert venue.currencies

    def test_the_verified_route_really_carries_a_verified_source(self) -> None:
        registry = fixture.six_state_registry()
        route = registry.routes[fixture.VERIFIED_ROUTE]
        assert not prov.is_unverified(route.legs[0].provenance)
        assert route.legs[0].provenance.sources
