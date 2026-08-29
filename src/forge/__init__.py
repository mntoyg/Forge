"""Forge - an open-source, AI-first coding assistant for the terminal.

This package is organised as a Clean Architecture. See
``docs/architecture/overview.md`` for the authoritative description; the short
version is that dependencies point inwards only::

    presentation -> application -> domain
    cli          -> application -> domain
    infrastructure implements ports declared by domain/application

Nothing under :mod:`forge.domain` may import a framework, an SDK, or perform
I/O of any kind.
"""

__all__ = ["__version__"]

__version__ = "0.0.1"
