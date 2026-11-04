# ADR-0017 - Choose Python package distribution channels

## Status

Accepted - owner selected option B on 2026-11-04; distribution name pending

## Context

Forge is prepared at version `0.1.0` and now has user-facing commands:
`forge debug`, `forge debug --diff`, `forge inspect`, `forge review`, and
`forge explain`. The existing tag-triggered release workflow runs the quality
gate, builds with `uv build`, and attaches `dist/*` to a GitHub Release. It does
not upload to a package index. `.forge/workflows/release.md` says PyPI is out
of scope because there is no user-facing capability yet; that rationale no
longer reflects the current product.

The project metadata currently declares distribution name `forge-cli`, while
the console script is `forge` and the import package is `src/forge`. PyPI
already has an unrelated `forge-cli` project, released in 2013 for Linux
system configuration. Forge must not publish under that name. See the
[existing PyPI project](https://pypi.org/project/forge-cli/) and PyPI's
[project-name guidance](https://docs.pypi.org/project-management/choosing-a-name/).
No replacement name has been selected or checked; a PyPI name must be chosen
by the owner and checked for availability and confusing similarity immediately
before project creation. A lookup does not reserve a name.

If the distribution name changes, the affected surfaces are:

- `pyproject.toml`'s `project.name` and the corresponding project entry in
  `uv.lock`;
- built wheel and source archive filenames and their distribution metadata;
- install, upgrade, and dependency references by distribution name in user
  documentation and downstream requirements/lockfiles.

The source import `forge`, files under `src/forge/`, the `forge` console
script, and `forge --version` do not need to change. Source users who run
`uv sync` will need the regenerated lockfile; anyone naming this distribution
as `forge-cli` in an external dependency or lockfile will need to update that
reference. No external-user inventory is available.

There are independent release-readiness blockers, regardless of channel:
`docs/guides/getting-started.md` and `docs/architecture/data-flow.md` show
`forge 0.0.1` even though package metadata is `0.1.0`. Also, the release
preflight rejects a dirty worktree; this checkout currently has the user's
unrelated `.forge/agents/claude.md` edit. Neither issue is resolved by this
proposal.

## Decision

The owner selected option B: keep GitHub Releases and add PyPI through Trusted
Publishing. This authorizes implementation planning for that channel, but not
package-name changes, PyPI account or publisher setup, tagging, or publication.
Those steps require an owner-selected distribution name and the remaining
acceptance checks below.

### A. GitHub Release artifacts only

Keep the current tag-triggered GitHub Release as the sole release channel.
The existing workflow already builds and attaches the wheel and source
archive. Contributors and users can continue to install from a source checkout
with `uv sync --all-groups`; users who download a wheel can install that exact
file directly. There is no PyPI project or publishing identity to manage.

This is the smallest operational change and avoids adding an index-publishing
job. It does not provide the familiar `pip install` or `uv tool install`
experience from a package index. A wheel installed by direct file may still
carry `forge-cli` metadata; users must not use that name to upgrade from PyPI,
where it resolves to the unrelated project. If artifacts are intended as a
supported install path, the owner must decide whether to rename the metadata
anyway and check the candidate name before release.

GitHub remains part of the supply chain: the tag, release workflow, its action
dependencies, and the repository's release permissions must be protected.
This option avoids a PyPI credential and OIDC trust configuration but does not
make a GitHub-built artifact inherently trustworthy. Maintenance is limited to
the existing release workflow, attached assets, and source-install guidance.

### B. GitHub Release plus PyPI via Trusted Publishing

Keep the GitHub Release for release notes and attached artifacts, and publish
those same built distributions to PyPI from GitHub Actions using PyPI Trusted
Publishing. This offers normal `pip`/`uv tool install` and upgrade behavior
alongside the existing release page. It requires changing `project.name` to an
owner-selected, PyPI-available name before the first upload; `forge-cli` is
excluded. The import package and console script can remain `forge`.

PyPI Trusted Publishing uses GitHub Actions OIDC and short-lived upload
credentials instead of a long-lived PyPI API token. It still trusts the
configured repository, workflow, and authorized actors; it does not establish
that the source or artifact is safe. The publisher must be restricted to the
specific release workflow, and `id-token: write` should be granted only to the
publishing job. A protected GitHub environment is recommended. See PyPI's
[Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/) and
[security model](https://docs.pypi.org/trusted-publishers/security-model/).

This option adds the name migration, PyPI project ownership and publisher
configuration, another workflow integration to maintain, and release failure
modes if either destination is unavailable. It consumes additional GitHub
Actions time; no direct service-cost estimate is made here. The release should
build once and publish the same immutable `dist/*` files to both destinations,
with checksums compared, to avoid channel drift. Trusted Publishing reduces
credential exposure but does not replace workflow hardening or artifact review.
The publisher's identity is only as trustworthy as the release workflow and its
actions, so implementation must review and pin the publishing action and use
job-scoped permissions.

### Why PyPI-only is not one of the proposed choices

PyPI-only would provide index-based installation, but it would remove the
existing GitHub Release page, its generated release notes, and attached
artifacts unless those surfaces were separately recreated. It would replace
rather than complement the current release contract. It could be reconsidered
if the owner deliberately retires GitHub Releases; it is not the minimal
extension of today's workflow.

## Alternatives Considered

- **A. GitHub Release artifacts only.** Lowest operational overhead and no
  registry identity, at the cost of a less convenient install path and the
  unresolved `forge-cli` metadata collision for directly installed artifacts.
- **B. GitHub Release plus PyPI Trusted Publishing.** Preserves release notes
  and assets while adding package-index installation with short-lived OIDC
  credentials. It costs a distribution-name migration, owner setup, and
  ongoing workflow/security maintenance.
- **PyPI-only.** Useful for index installation but drops the existing GitHub
  release notes and artifact surface; therefore not proposed as a replacement
  without a separate owner decision.

## Acceptance Criteria

An accepted decision and any later implementation must meet these checks:

1. The owner explicitly selects A or B. This Proposed ADR alone is not approval
   to change configuration or publish.
2. Before any PyPI project is created, the owner selects a candidate name;
   check its live PyPI availability and PyPI naming/similarity rules on the day
   of setup. Do not use `forge-cli`, and do not treat an availability lookup
   as a reservation.
3. If metadata is renamed, update `project.name`, regenerate and commit
   `uv.lock`, update all install/dependency references and release asset
   expectations, and verify `src/forge` imports and the `forge` script remain
   unchanged. Downstream references using the old distribution name must have
   a documented migration.
4. For A, a tagged release that passes the full quality gate produces a wheel
   and source archive attached to the GitHub Release, with the release version
   and install path documented. For B, one tagged build produces the artifacts
   uploaded to both GitHub and PyPI; compare SHA-256 checksums to prove both
   destinations received identical files.
5. For B, verify the PyPI Trusted Publisher matches the intended repository,
   release workflow, and protected environment; grant `contents: write` only
   to the GitHub Release job and `id-token: write` only to the publishing job;
   store no long-lived PyPI upload token; and review/pin the publishing action.
   Verify the published project page and artifact provenance after a separately
   approved first publication.
6. In an isolated environment, install through the documented path (A: source
   checkout or a supported downloaded artifact; B: the PyPI distribution) and
   verify `forge --version` reports the release version and the CLI starts
   without an API key. Do not make live provider calls.
7. Resolve the stale `0.0.1` documentation examples and obtain a clean-worktree
   release preflight before cutting `v0.1.0`; these are separate blockers,
   not criteria that select A or B.

## Consequences

Until the owner chooses A or B and, for PyPI, selects and checks a distribution
name, the channel and package identity remain undecided. No code, workflow,
metadata, account, tag, or publication change follows from this proposal.
