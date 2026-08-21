"""Orchestration and the typed result schema. The UI and the CLI are both clients.

Per owner decision D-B the web UI framework is deliberately deferred until the
result schema has stabilised against real output; this layer is designed as the UI's
only contract so that choice stays cheap.

Principle III: orchestration lives here, never in the core and never in the CLI.
Every result carries its run manifest -- scenario hash, code version, objective,
seed, and the provenance of every input.
"""
