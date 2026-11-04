# ADR-0018 - Select the PyPI distribution name

## Status

Accepted - owner selected `mntoyg-forge` on 2026-11-05

## Context

ADR-0017 selects GitHub Releases plus PyPI Trusted Publishing and explicitly
leaves the distribution name to the owner. Forge's current distribution name,
`forge-cli`, conflicts with an unrelated PyPI project. The import package and
CLI command are both named `forge`; this decision concerns only the installable
distribution name.

The owner selected `mntoyg-forge`. On 2026-11-05, direct requests to the
[PyPI project page](https://pypi.org/project/mntoyg-forge/) and
[PyPI JSON API](https://pypi.org/pypi/mntoyg-forge/json) returned HTTP 404.
This indicates that neither endpoint exposed a project under that name at the
time of lookup. PyPI says a name can still be unavailable when no project page
exists, including due to similarity, reservation, or administrative policy;
the lookup does not reserve the name. See [PyPI's name-selection
policy](https://docs.pypi.org/project-management/choosing-a-name/).

## Decision

Use `mntoyg-forge` as Forge's intended PyPI distribution name. Keep the import
package `forge` and console script `forge` unchanged. During project creation,
confirm PyPI accepts the name. If PyPI rejects it, stop and ask the owner to
select another name; do not silently substitute one.

This ADR records the name selection only. It does not authorize creating the
PyPI project, changing package metadata, configuring Trusted Publishing,
tagging, or publishing. Those changes follow a separate implementation review
under ADR-0017 after project setup eligibility is confirmed.

## Alternatives Considered

- **Keep `forge-cli`.** Rejected because an unrelated project already occupies
  that PyPI name.
- **Use the generic name `forge`.** Rejected because an unrelated project
  already occupies that PyPI name.
- **Use the owner-selected `mntoyg-forge`.** Selected as a distinct name that
  keeps the existing Forge brand recognizable. The direct lookup found no
  project, subject to PyPI's final eligibility decision.

## Consequences

- Users will install the package as `mntoyg-forge`, while the command and
  Python import remain `forge`.
- Metadata, lockfile, installation docs, and release automation must use the
  selected distribution name when implementation is approved.
- A 404 result is time-bound and is not a reservation. Another user could
  register the name before setup, and PyPI may reject it under its naming
  policy.
