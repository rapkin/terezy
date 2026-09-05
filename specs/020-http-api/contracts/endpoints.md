# Contract: the route table

The **set** is built from `categories.py` and asserted by the suite; this file is the shape of a
registration, not a second copy of the table (that is `data-model.md`, which is itself checked
against the resolver in both directions).

Every route below takes a **required** `as_of` (ISO date) and, on the six scenario-taking
categories, an optional `scenario_id`. There is no `display` parameter: the switch is deferred.

```
GET /{category}                        listing   — keyed categories
GET /{category}/{id}                   read      — keyed categories
GET /{category}                        singleton — the seven
GET /cpi/{id}/observations             ?from=&to=      two-ended or omitted
GET /official-rates/{id}/observations  ?from=&to=      two-ended or omitted
GET /questions/{id}/answer             the answer and its manifest
GET /registry                          the per-category summary
GET /openapi.json                      rendered from the running application
```

**Route groups own a first segment.** Twenty-five categories plus `registry` plus `openapi.json` is
twenty-seven owners; `/questions/{id}/answer` and `/cpi/{id}/observations` are inside their
category's group rather than new owners of one. The check is over owners, not paths.

**Not served**, asserted as absences over the route table:

- anything under `data/observations/` (FR-048);
- a question built from request parameters — the only answer route names a declared id (FR-043,
  SC-026a);
- the framework's two documentation routes, and any other route serving markup or a script
  (FR-031).

**Headers.** No cross-origin allowance at all — 021 is same-origin in both of its modes — and a
`Host` allowlist of loopback hosts, which is what refuses and the only check that sees a
DNS-rebinding request.
