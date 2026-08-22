"""Income streams: where the owner's money arrives, in what currency, at what venue.

**Per-owner data, deliberately not in ``terezy.core.routes``.** This package exists as a
separate package from ``routes`` for one reason, and it is Principle VII's: a stream is
*this owner's* salary -- its amount, its cadence, the account it lands in -- while a route
is a curated public fact about a corridor that every owner shares. Putting the two in one
package would make the per-user/curated boundary a matter of reading field names, and that
boundary is the thing that makes multi-user cheap later (constitution, Principle VII;
plan.md, "Structure Decision"). The same split is mirrored in the data layer:
``data/streams/`` is per-owner, ``data/routes/`` and ``data/channels/`` are curated.

Two consequences of the split that are worth stating where the code lives:

* **Every record here carries ``owner_id``**, from the first commit, while there is exactly
  one owner and no authentication. An unused column is free; retrofitting tenancy is not.
* **A stream is not an observation.** An owner's own salary needs no citation -- it is a
  statement of fact by the only person who can make it -- so stream declarations are exempt
  from the ``source``/``retrieved_on``/``verified_on`` requirement, exactly as
  ``data/scenarios/`` already is. Nothing here may therefore be given a fabricated source
  to satisfy a provenance check.

**Why a stream matters to a cost at all.** Principle VI: access cost is never quoted per
instrument or per destination, only per ``(instrument x income stream x route)``. The same
USD acquisition is nearly free funded from USD contract income and 5-10% expensive funded
from a UAH salary (``SIMULATOR_SPEC.md`` §4.3.1). The stream is the term that makes that
difference computable, which is why ``FundingPath`` cannot be constructed without one.

The records and the deployable-capacity function arrive with User Story 2 (T024). This
package is created ahead of them so the boundary above exists before anything is tempted
to put a stream in ``routes``.
"""
