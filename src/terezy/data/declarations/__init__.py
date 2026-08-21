"""Declared domain knowledge: read the files, validate them, build core records.

**Validation lives here, never in core.** The core defines the domain types -- bond
terms, tax classes, provenance, money -- as plain frozen dataclasses that know nothing
about files, TOML or validation libraries. This package reads and validates the files
and constructs those core types (research.md D1).

The consequence worth protecting: the core's bond arithmetic can be tested by
constructing terms directly in code, with no file on disk anywhere near the sum. That
is what makes the D1 worked example a check of the engine rather than a check of the
loader.

Standing rules:

* **Fail loudly, name the file and the field.** A malformed value, an unrecognised
  field, a missing required field, a duplicate identifier or a reference to an
  undeclared tax class stops the load (FR-016). No default is substituted for anything
  absent.
* **No validation-library type crosses this boundary.** ``pydantic`` is used inside
  this package and adapted into the project's own error record; a raw
  ``ValidationError`` reaching a caller is a leak (research.md D6).
* **Provenance is attached here or not at all.** This is the one place outside
  ``core.primitives.money`` permitted to construct money directly, because it is where
  declared values enter the system carrying their cited source.
"""
