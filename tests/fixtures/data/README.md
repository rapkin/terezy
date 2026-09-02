# `tests/fixtures/data/` — the invented declarations, and nothing else

An **overlay** on the shipped `data/` root, not a data root of its own. `tests/data_roots.py`
copies `data/` and then this tree over it; a file here whose path matches a shipped one
replaces it, and one whose path does not joins it.

Every declaration here is invented, and the shipped registry carries only real securities
(owner decision, 2026-09-02). Each one is the sole example of a live mechanism, which is why
none was retired: **retiring one deletes the only reachable case of the mechanism, and the
deletion looks like tidying.** `tests/contract/test_every_fixture_says_what_it_is_for.py`
asserts that this table names every file below it and no other.

| File | The mechanism it is the only example of |
|---|---|
| `instruments/ovdp_synthetic_a.toml` | A bond declared generatively — rate, periodicity, issue date — with the schedule computed. Feature 001's hurdle and `tests/golden/ovdp_synthetic_a.golden.txt`. |
| `instruments/ovdp_synthetic_b.toml` | A second generative bond differing in its conventions and its minimum ticket, so no test can pass by there being one. |
| `instruments/ovdp_enumerated_a.toml` | The enumerated half of the pair `tests/golden/test_enumerated_matches_generative.py` compares: one schedule, two declaration forms. |
| `instruments/ovdp_enumerated_mirror.toml` | The generative half of that pair. |
| `instruments/enumerated_out_of_order.toml` | 013 FR-020a: a transcription recording the source's own row order while paying in date order. The real issue it was modelled on, `UA4000235865`, turned out **not** to be out of order — the seller published it wrongly — so no real instance is left. |
| `instruments/enumerated_taxable_x.toml` | 013 FR-010: an enumerated schedule whose coupons are taxable, so premium netting has something to net against. Every real ОВДП here is exempt. |
| `instruments/synthetic_fund_c.toml` | A fund whose liquidity terms, spread, peg and tax schedule all differ from the two real Inzhur funds, so a fund refusal has something to refuse. |
| `access/fixtures.toml` | How each of the above is reached, priced and labelled. Beside `data/access/instruments.toml` rather than replacing it: `access/` is globbed and the two merge. |
| `seeds/owner-001.toml` | Two opening lots, one with a known basis and one estimated, so an estimated basis has a lot to propagate from. **Replaces** the shipped seeds file: a data root resolves at most one. |
| `tax/synthetic_fixture.toml` | A second jurisdiction whose rates differ per income kind, so a payment's declared label is provably load-bearing (013 FR-010). |
| `tax/timing/synthetic_fixture.toml` | Its assessment rules, whose category **nets** — the case 013 FR-026 requires exercised rather than warned about, and which Ukraine's own `exempt_securities` cannot show. |

`scripts/check_provenance.py` scans this tree through the composed root, in
`tests/contract/test_provenance_gate.py`: every price here is invented and every `verified_on`
is empty, and the gate treats an empty `verified_on` as an unverified value rather than an
error — so the citations still have to be well formed and dated.
