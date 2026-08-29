# Architecture Change Workflow

Use this when a change would alter a structural decision: the layers, the
dependency direction, an external service, the dependency set, or the public
CLI contract.

**No implementation starts before the ADR is accepted.**

## 1. Recognise it

`.forge/context/decisions.md` lists the triggers. The most common ones in
practice:

- "I need to add a library for this."
- "The use case needs to call the provider directly."
- "This would be simpler if the domain knew about the CLI."
- "We should cache this."

Every one of those is an architecture change wearing a small hat.

## 2. Stop and state the conflict

Before proposing anything, write down:

- What you are trying to accomplish.
- Which rule or ADR blocks it.
- Why the obvious workaround is not acceptable.

## 3. Write the ADR

Copy an existing record in `docs/architecture/decisions/` and follow its
structure exactly:

```markdown
# ADR-XXXX - <Title>

## Status
Proposed

## Context
## Decision
## Alternatives Considered
## Consequences
```

Numbering is sequential and never reused. A new ADR that replaces an old one
sets the old one to `Superseded by ADR-XXXX` and says so in its own `Context`.

Rules for a good ADR here:

- **Context** describes the forces, not the solution.
- **Alternatives** lists options genuinely considered, each with why it lost.
  An ADR with one alternative called "do nothing" is not a decision record.
- **Consequences** states the costs as plainly as the benefits, including what
  becomes harder.

## 4. Architecture review

The proposal goes to review before acceptance:

- ChatGPT reviews the design coherence and the layer implications.
- Gemini reviews failure modes, scalability, reliability, and cost.
- A human accepts or rejects.

Only a human moves an ADR to `Accepted`.

## 5. Update the derived documents

An accepted ADR is not finished until these agree with it:

- `docs/architecture/overview.md`
- `docs/architecture/components.md`
- `docs/architecture/data-flow.md`
- `.forge/context/architecture.md`
- `.forge/context/decisions.md` (index row)
- `pyproject.toml`, if the dependency set or tool config changed
- `.forge/context/conventions.md`, if the rules for writing code changed

Documentation that contradicts an accepted ADR is a defect. Fix it in the same
PR.

## 6. Implement

Now, and only now, follow [development.md](development.md) from the
implementation-plan step. The PR references the ADR by number.

## 7. If the ADR is rejected

Record it anyway with `Status: Rejected` and the reason. A rejected ADR is
valuable: it stops the same proposal arriving again in six months with no
memory of why it lost.
