# Guides

Task-oriented documentation for people using Forge.

Each guide arrives with the capability it describes, in the same pull request.
Writing one ahead of the feature produces documentation that is wrong on the
day it is committed.

## What goes here

A guide answers "how do I do X with Forge?" - as opposed to:

| Directory | Answers |
| --- | --- |
| `docs/product/` | What is Forge, and what will it do? |
| `docs/architecture/` | How is it built, and why? |
| `docs/development/` | How do I contribute to it? |
| `docs/guides/` | How do I use it to get something done? |

## Available

- **[Getting started](getting-started.md)** - install, configure a key, analyse
  your first file, read the output, and use the exit codes in a script.

## Planned

- **Debugging a change** - working against a diff rather than a file
  *(with Phase 3)*
- **Machine-readable output** - consuming Forge from another tool
  *(with Phase 4)*

See `docs/product/roadmap.md` for phase sequencing.

## Writing a guide

- Start from the user's task, not from the feature.
- Show the real command and its real output.
- Say what it does **not** do. A guide that only shows success is a
  disappointment waiting to happen.
- Keep examples runnable against files in `examples/`.
