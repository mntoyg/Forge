# CLAUDE.md

**Read [`AGENTS.md`](AGENTS.md) first.** It is the entry point for every AI
agent working in this repository, and this file adds nothing to it.

It is kept separate only because Claude Code loads `CLAUDE.md` automatically.
Duplicating the rules here would create a second source of truth, and the two
copies would drift.

Two files matter most, in this order:

1. [`.forge/context/project.md`](.forge/context/project.md) - what this is
2. [`.forge/context/status.md`](.forge/context/status.md) - where we are today,
   what is next, and what would otherwise be rediscovered the hard way

Your role, if you are Claude Code, is
[`.forge/agents/claude.md`](.forge/agents/claude.md): Lead Implementation
Engineer. You implement approved designs. You do not decide the architecture -
when a design is missing or looks wrong, say so and ask.

Before finishing, update `.forge/context/status.md` and run:

```bash
uv run python scripts/check.py
```
