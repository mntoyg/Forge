# Vision

## What Forge is

Forge is an open-source, AI-first coding assistant that lives in the terminal.

It is not a chat window that happens to know about code. It is a command-line
tool whose commands are shaped by what a developer actually does: understand a
file, find out why something broke, review a change, generate a piece, improve
what is already there.

## The problem

A developer hitting an unfamiliar failure has three bad options:

1. **Read the code alone.** Reliable, but slow when the codebase is unfamiliar
   or the stack trace points somewhere unhelpful.
2. **Paste into a chat assistant.** Fast, but it means leaving the terminal,
   copying context by hand, losing the surrounding repository, and pasting
   source code into a browser tab.
3. **Use an IDE assistant.** Good inside the editor, but it does not help in a
   CI log, over SSH, in a container, or in any of the places terminal work
   actually happens.

The gap is a tool that has the repository context already, runs where the work
is happening, and returns a structured answer instead of a conversation.

## Who it is for

**Primary: the working developer in a terminal.** Someone comfortable with
git, a shell, and their language's tooling, who wants a faster path from
"this is broken" to "I understand why". They value determinism, readable
output, and not having to trust a black box.

**Secondary: teams standardising how they use AI.** Forge is configuration and
prompts in a repository, so a team can agree once on how code is reviewed or
explained, and get the same behaviour for everyone.

**Also: contributors to Forge itself.** The repository is deliberately
structured so that both humans and AI agents can work in it safely. That is a
product goal, not an accident.

## What makes it different

- **Terminal-native.** Composable, scriptable, and available wherever a shell
  is.
- **Repository-aware.** It reads the actual files and the actual git history,
  not what someone remembered to paste.
- **Provider-agnostic by design.** The AI provider sits behind a port. Swapping
  it is a configuration change, not a rewrite.
- **Transparent.** It shows what it read and what it concluded. A tool you
  cannot audit is a tool you cannot trust with your codebase.
- **Safe by default.** It never modifies files without explicit approval and
  never executes code it was given.

## MVP scope

The first release does one thing well:

```bash
forge debug <file>
```

Read a source file, analyse it with an AI provider, and report likely problems
in a structured, readable form. Read-only. No file modification, no execution.

That is the whole MVP. See [requirements.md](requirements.md) for the specifics
and [roadmap.md](roadmap.md) for what follows.

## Non-goals

Explicitly out of scope, now and for the foreseeable future:

- **Autonomous agents.** Forge does not run unattended loops or self-directed
  multi-step plans.
- **Automatic code modification.** Forge may propose a change; a human applies
  it.
- **Executing user code.** Forge reads and reasons. It does not run what it
  reads.
- **Being an IDE or an editor.** It complements them.
- **A hosted service.** Forge is a local CLI using the user's own API key.
- **Training or fine-tuning models.**
- **A vector database or a retrieval framework.** File and git context is
  enough for the problems in scope. Adding retrieval would be an architectural
  decision requiring its own ADR.
- **Supporting every language on day one.** Depth over breadth.

## Principles

1. **The developer stays in control.** Forge proposes; the human decides.
2. **Deterministic where it can be.** Everything except the model call itself
   should be reproducible and testable.
3. **Honest output.** When the model is uncertain, the output says so.
4. **Small and comprehensible.** A tool that a single developer can read the
   source of in an afternoon.
5. **Cost-aware.** Every request spends the user's money. Treat that as a
   design constraint.
