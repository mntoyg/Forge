# Forge - the prompt that starts the next chat

Generation 2 · written 2026-09-17 · by the chat that suspended ADR-0013.
The user pastes this whole file into a new chat.

You are continuing work on **Forge**, an AI-first coding assistant CLI (Python
3.13, uv, Typer, Clean Architecture) at `D:\code-project\Forge` - not the
session's working directory. Run every command there. **Reply to the user in
Thai**; code, commits, pull requests and repository documents stay in English.

## 1. Start cold, in this order

1. `AGENTS.md` - the entry point and the rules every agent follows.
2. `.forge/context/project.md`, then `.forge/context/status.md`. **`status.md`
   wins when it disagrees with this prompt**: it changes in every pull request.
3. `.forge/context/decisions.md`, then ADR-0011, 0012 and 0013 - their
   measurement tables, not only their decisions.
4. Check reality: `git fetch`, `git log --oneline -5 origin/main`, `gh pr list`,
   `gh repo view mntoyg/Forge --json visibility`.
5. Load `mcp__ccd_session_mgmt__get_usage` with ToolSearch and call it. Tell the
   user the context and weekly plan percentages before any large task - every
   chat shares the weekly plan.

## 2. The snapshot this prompt was written against

- `main`: 368 tests pass, 1 skipped on Windows; CI green on ubuntu, macOS and
  Windows; no open pull requests.
- **ADR-0013 is suspended.** It chose marked windows (Option A, at most 8 calls
  per file); its own required measurement showed a 300- or 800-line marked
  window is not read to its end. Nothing was built.
- `0.1.0` is prepared and **not tagged**; the repository is **private**. Both are
  the user's calls.
- `mntoyg/Forge-archive` carries the user's personal email in its history.
  **It must never be made public.**
- Weekly plan 84% on 2026-09-17, resetting 2026-09-19. Handed off at 64% context.

## 3. The task

**Re-decide how a long file is reviewed in full.** The user chose Option A on a
recommendation this measurement undercut - say so plainly with the new numbers.

1. **Measure, then ask.** Get approval for the spend first, stating the cost:
   marked windows of **25, 50 and 100 lines** at ~44k tokens with the defect on
   the window's last line, twice each (~6 calls, ~4 US cents); and a **~300-line
   chunk sent alone**, defect last, twice (cents) - does Option B's premise hold?
2. **The probe** (the last one lived in a scratchpad and is gone): build
   `SourceFile(path, content)` from text, which skips the workspace check; mark
   with `build_request(source, changed=frozenset(window))`; call `OpenAIProvider`
   from `load_settings()`; read with `parse_findings`. File:
   `.venv/Lib/site-packages/click/core.py` (3,806 lines). Defect: a function
   `summarize_option_lengths` ending in an unguarded `total / len(options)`,
   appended last. Commit it as `scripts/probe_attention.py` so the ADRs'
   evidence can be re-run.
3. **Show a cost table** - A at the window size that works, against B - and get
   a decision.
4. **Write ADR-0014 superseding ADR-0013**, then build with tests at the right
   level, then verify live once, asking first.

If the user asks for something else, do that instead.

## 4. Rules that bite

- Work directly on `main`; run checks, review the diff, commit, and push to
  `origin/main`. Never force-push or bypass branch protection; stop if rejected.
- **Never call a real provider without asking**, cost stated first. The key is
  in `.env`: never print, copy, or commit it.
- `uv run python scripts/check.py` before claiming done, with `set -o pipefail`
  so a failing gate piped through `tail` cannot let a commit through.
- Conventional Commits with a *why* body and the `Co-Authored-By` trailer, passed
  with `-F` or a quoted heredoc. **Check every number a message claims.**
- Update `status.md` in the same commit; a test holds it to 150 lines.
- An accepted ADR is superseded, never rewritten; results and status may be added.

## 5. Lessons carried forward

Each cost real time once. Keep only what is still true and not enforced by a
test or written in `status.md`.

- **Run the measurement a decision depends on before asking the user to
  decide.** ADR-0013 was accepted on Option A and suspended hours later by the
  measurement it had deferred.
- A Python heredoc containing triple-quoted strings can break bash quoting.
  Write the script to the scratchpad with the Write tool, then run it.
- `gh pr merge --delete-branch` closes any pull request stacked on that branch
  for good. Do not stack; or rebase onto `main` and retarget first.
- `gh pr checks --watch` straight after a push prints "no checks reported" and
  exits. Wait until `gh run list` shows the run.
- `forge` outside the repository finds no `.env` and exits 3. In a probe
  repository, load the key unechoed: `set -a; . D:/code-project/Forge/.env; set +a`.

## 6. The handoff loop

This keeps the chain of chats alive. **Carry it into every new version of this
file**, changed only where the ending chat found a real flaw. A test fails the
build if it disappears.

**When.** Call `get_usage` at the start, after each merged pull request, and
before anything large. **Before a task, judge whether it can reach a clean state
before 70%; if not, do its largest step that can - a measurement, an ADR, a
failing test - and hand off.** At **about 70% of the context window**:

- a task in progress: finish it cleanly - gate green, committed, pushed, pull
  request merged or clearly left open - then hand off;
- nothing in progress: hand off now.

Unreadable percentage: hand off early rather than late. The user saying 70% is
authoritative.

**How.** Rewrite this file, `.forge/NEXT_PROMPT.md`, to be *better* than the
version you started from - never a copy carried forward:

1. Increment the generation; update the date.
2. Rebuild section 2 from `git`, `gh` and `get_usage`, never from memory.
3. Replace section 3 with the true next task, every decision the user made in
   this chat, and whatever the next chat would otherwise rediscover.
4. Section 5: add at most three lessons that cost real time; delete any that are
   obsolete, enforced by a test, or already in `status.md`.
5. Answer the improvement check and act on every "yes".
6. Under 200 lines, enforced by a test - and no longer than the version before.

**Improvement check**, against the ending chat:

- Did it ask the user anything this file could have answered, or ask before it
  had the evidence the answer depended on?
- Did any instruction here prove wrong, stale, or rightly ignored?
- Did anything cost more than a few minutes that a sentence would have saved?
- Is the new version no longer than the old while carrying more? **Count it.**

**Then.** Commit it directly to `main` with the `status.md` update and push.
Paste the **complete** file to the user in **one** code
block, and under it three lines: what changed, why this version is better, and
the context and weekly plan percentages at hand-off.
