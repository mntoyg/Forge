# Guides

Task-oriented documentation for people using Forge.

This directory is deliberately empty of user guides right now, because Forge
has no user-facing capability yet. Writing a guide for something that does not
exist produces documentation that is wrong on the day it is committed.

## What goes here

A guide answers "how do I do X with Forge?" - as opposed to:

| Directory | Answers |
| --- | --- |
| `docs/product/` | What is Forge, and what will it do? |
| `docs/architecture/` | How is it built, and why? |
| `docs/development/` | How do I contribute to it? |
| `docs/guides/` | How do I use it to get something done? |

## Planned guides

These arrive with the features they describe, in the same pull request:

- **Getting started** - install, configure a key, run your first command
  *(with Phase 1)*
- **Debugging a file** - what `forge debug` does, how to read the output, and
  what it will not tell you *(with Phase 2)*
- **Configuring a provider** - environment variables, model selection,
  self-hosted endpoints *(with Phase 1)*
- **Using Forge in CI** - non-TTY output, exit codes, scripting *(with Phase 4)*

See `docs/product/roadmap.md` for phase sequencing.

## Writing a guide

- Start from the user's task, not from the feature.
- Show the real command and its real output.
- Say what it does **not** do. A guide that only shows success is a
  disappointment waiting to happen.
- Keep examples runnable against files in `examples/`.
