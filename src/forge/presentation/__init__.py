"""Presentation layer - rendering and formatting.

Turns application results into something a human can read in a terminal: Rich
tables, panels, diffs, and plain-text fallbacks for non-TTY output.

Hard rules:

* May import from :mod:`forge.domain` and :mod:`forge.application`.
* Must not import from :mod:`forge.infrastructure`.
* Contains no business logic and makes no decisions - it only renders what it
  is given.
"""
