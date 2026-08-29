"""Domain layer - the heart of Forge.

Contains entities, value objects, domain services, and the port (interface)
definitions that the outer layers must satisfy.

Hard rules:

* No imports from :mod:`forge.application`, :mod:`forge.infrastructure`,
  :mod:`forge.cli`, or :mod:`forge.presentation`.
* No third-party framework or SDK imports (no Typer, Rich, OpenAI, httpx,
  GitPython, Loguru).
* No I/O: no filesystem, network, subprocess, clock, or randomness. Those
  arrive through ports.
* Everything here must be unit-testable with zero setup.

The standard library and Pydantic-free plain classes / dataclasses are enough.
"""
