"""Application layer - use cases and orchestration.

Contains the use cases that express what Forge *does*, expressed purely in
terms of domain types and domain-declared ports. A use case receives its
collaborators through its constructor (dependency inversion); it never
constructs an adapter itself.

Hard rules:

* May import from :mod:`forge.domain`.
* Must not import from :mod:`forge.infrastructure`, :mod:`forge.cli`, or
  :mod:`forge.presentation`.
* Must not know it is being driven by a CLI, nor which AI provider is in use.
"""
