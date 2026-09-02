# `tests/fixtures/data/` — the invented instruments, and nothing else

An **overlay** on the shipped `data/` root, not a data root of its own. `tests/data_roots.py`
copies `data/` and then this tree over it; a file here whose path matches a shipped one
replaces it, and one whose path does not joins it.

Every instrument declared here is invented. The shipped registry carries only real securities
(`data/README.md` rule 5 admits both, and the owner's decision of 2026-09-02 keeps the invented
ones out of what ships), so this is where the examples live.

Each is the only example of a live mechanism, which is why none was retired:

| File | The mechanism it is the only example of |
|---|---|
| `instruments/ovdp_synthetic_a.toml` | A bond declared generatively — rate, periodicity, issue date — with the schedule computed. Feature 001's hurdle and `tests/golden/ovdp_synthetic_a.golden.txt`. |
| `instruments/ovdp_synthetic_b.toml` | A second generative bond differing in its conventions and its minimum ticket, so a test cannot pass by there being one. |
| `instruments/ovdp_enumerated_a.toml` | The enumerated half of the pair `tests/golden/test_enumerated_matches_generative.py` compares: same paper, two declaration forms, one schedule. |
| `instruments/ovdp_enumerated_mirror.toml` | The generative half of that pair. |
| `instruments/enumerated_out_of_order.toml` | 013 FR-020a: a transcription that records the source's own row order while paying in date order. The real issue it was modelled on, `UA4000235865`, turned out **not** to be out of order — the seller published it wrongly — so there is no real instance left. |
| `instruments/enumerated_taxable_x.toml` | 013 FR-010: an enumerated schedule whose coupons are taxable, so premium netting has something to net against. Every real ОВДП here is exempt. |
| `instruments/synthetic_fund_c.toml` | A fund declaring terms the two real Inzhur funds do not, so a fund refusal has something to refuse. |

`scripts/check_provenance.py` scans this tree through the composed root, in
`tests/contract/test_provenance_gate.py`: every price here is invented, every `verified_on` is
empty, and the gate treats an empty `verified_on` as an unverified value rather than an error —
so the citations still have to be well-formed and dated.
