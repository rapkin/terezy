"""Two applications in one process, and what they cost the second time.

`envelopes.container` mints a frozen dataclass per category, and both folds over it -- the shape
plan and the pydantic model -- memoise by the record's identity. A container minted per call
therefore missed both caches and filled them instead: measured 2026-09-11, 57 records and 3.75 MB
per `create_app`, held for the life of the process by caches with no eviction.
"""

from __future__ import annotations

from terezy.api.http import document, envelopes, models, service, shapes
from tests.data_roots import SHIPPED

DATA_ROOT = SHIPPED


def test_one_container_is_built_once_for_one_name_and_one_field_set() -> None:
    built = envelopes.listing_of("instruments", series=False)
    assert envelopes.listing_of("instruments", series=False) is built
    assert envelopes.listing_of("instruments", series=True) is not built


def test_a_second_application_reuses_the_first_ones_types() -> None:
    """Identity, not equality: the caches are keyed by the record object, so a record that is
    merely equal to a cached one is a miss and the entry is duplicated."""
    service.create_app(DATA_ROOT)
    planned, modelled = len(shapes._MEMO), len(models._MODELS)

    service.create_app(DATA_ROOT)

    assert len(shapes._MEMO) == planned
    assert len(models._MODELS) == modelled


def test_two_applications_serve_one_document() -> None:
    """The property the memo must not break, and the reason it is safe: the document is a
    function of the category table, so a second application publishes the same contract."""
    first = document.rendered(service.create_app(DATA_ROOT))
    second = document.rendered(service.create_app(DATA_ROOT))
    assert first == second
