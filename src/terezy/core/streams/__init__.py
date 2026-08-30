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

"""
