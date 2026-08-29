"""CLI layer - the Typer command surface.

Each command is a thin adapter: parse and validate input, call a single
application use case, hand the result to :mod:`forge.presentation`, map errors
to exit codes. A command body that grows past a few lines is a sign that logic
has leaked out of the application layer.

Hard rules:

* May import from :mod:`forge.application`, :mod:`forge.domain`, and
  :mod:`forge.presentation`.
* Must not import from :mod:`forge.infrastructure`; dependencies are injected
  by :mod:`forge.main`.
"""
