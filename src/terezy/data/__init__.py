"""Data layer: providers, caching with provenance, the offline snapshot, manifests.

Most of the modelled instruments have no API, so curated, version-controlled,
human-maintained files are a first-class source here, not a fallback
(SIMULATOR_SPEC.md §7).

Two standing rules from Principle IV: a cache never holds synthetic or fallback
data, and a fetch failure never writes. Cache entries carry provenance -- source,
fetch time, and an explicit synthetic flag -- and synthetic data is rejected unless
it was asked for by name.
"""
