"""Infrastructure layer - adapters to the outside world.

Concrete implementations of the ports declared by the inner layers: AI provider
clients, HTTP transport, filesystem access, git inspection, configuration
loading, and logging.

Hard rules:

* May import from :mod:`forge.domain` and :mod:`forge.application` (to
  implement their interfaces).
* Must not be imported *by* those layers - wiring happens in
  :mod:`forge.main`.
* Every external SDK (OpenAI, httpx, GitPython, Loguru, Pydantic Settings)
  lives behind an adapter here and nowhere else.
"""
