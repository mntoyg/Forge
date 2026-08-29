# Adding a New Agent

Forge expects its set of agents to change. This file is the process for adding
one without eroding the rules that keep the others aligned.

## Before adding an agent, answer these

1. **What gap does it fill?** Name a task that no current agent does well. If
   the answer is "it could also implement features", the answer is no - that
   role is taken.
2. **What does it not do?** An agent without an explicit boundary drifts into
   every task and blurs the others.
3. **Where does it sit in the workflow?** Which step of
   `.forge/workflows/development.md` does it own, and who hands work to it?
4. **How is its output verified?** Every agent passes the same gate: tests,
   lint, types, review. There is no exemption for a new one.

## The file to write

Create `.forge/agents/<name>.md` with these sections, matching the existing
files:

```text
# <Name> - <Role title>

## Role
## Responsibilities
## Explicitly not
## Working agreement
## Definition of done
```

Then:

- Add a row to the role summary table in [README.md](README.md).
- If the agent changes the workflow, update the relevant file in
  `.forge/workflows/`.
- If the agent needs a reusable prompt, add it to `.forge/prompts/`.

## Rules a new agent inherits automatically

Everything under "Rules that bind every agent" in [README.md](README.md), plus
the source-of-truth hierarchy. A new agent file cannot grant itself an
exemption from an ADR, from the architecture, or from the quality gate. If it
appears to, the agent file is the thing that is wrong.

## Prompt-level integration

Whatever the agent is, its instructions should point at the same four context
files rather than restating them:

```text
.forge/context/project.md
.forge/context/architecture.md
.forge/context/conventions.md
.forge/context/decisions.md
```

Restating them creates a second source of truth that will drift. Point, do not
copy.

## Removing an agent

Delete its file, remove its row from the table, and note the removal in
`CHANGELOG.md` under `Changed`. If workflows referenced it, reassign those
steps explicitly rather than leaving them unowned.
