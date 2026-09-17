# Forge - the prompt that starts the next chat

Generation 2 · written 2026-09-17 · by the chat that suspended ADR-0013.
The user pastes this whole file into a new chat.

You are continuing work on **Forge**, an AI-first coding assistant CLI (Python
3.13, uv, Typer, Clean Architecture) at `D:\code-project\Forge`. That is not the
session's working directory: run every command there.

**Reply to the user in Thai.** Code, commits, pull requests and repository
documents stay in English.

## 1. Start cold, in this order

1. `AGENTS.md` - the entry point, and the rules every agent follows.
2. `.forge/context/project.md`, then `.forge/context/status.md`. **`status.md`
   wins whenever it disagrees with this prompt**: it is updated in every pull
   request, and this prompt is a snapshot.
3. `.forge/context/decisions.md`, then ADR-0011, ADR-0012 and ADR-0013 - read
   the measurement tables, not only the decisions.
4. Check reality before trusting any snapshot: `git fetch`,
   `git log --oneline -5 origin/main`, `gh pr list`, and
   `gh repo view mntoyg/Forge --json visibility`.
5. Load `mcp__ccd_session_mgmt__get_usage` with ToolSearch and call it. Tell the
   user the context percentage and the weekly plan percentage before any large
   task - the weekly plan is shared by every chat.

## 2. The snapshot this prompt was written against

- `main`: 368 tests pass (1 skipped on Windows); CI green on ubuntu, macOS and
  Windows. No open pull requests.
- **ADR-0013 is suspended.** It chose marked windows (Option A, at most 8 calls
  per file); its own required measurement then showed a 300- or 800-line marked
  window is not read to its end. Nothing was built.
- `0.1.0` is prepared and **not tagged**; the repository is **private**. Both are
  the user's calls - do neither unasked.
- `mntoyg/Forge-archive` carries the user's personal email address in its
  history. **It must never be made public.**
- Weekly plan 84% on 2026-09-17, resetting 2026-09-19. Handed off at 64% context.

## 3. The task

**Re-decide how a long file is reviewed in full.** The user chose Option A on a
recommendation the measurement then undercut; say that plainly when you bring
the new numbers.

1. **Measure first, then ask** - approval for the spend, with the cost stated:
   - marked windows of **25, 50 and 100 lines** at ~44,000 tokens, defect on the
     window's last line, twice each (~6 calls, ~4 US cents): the largest window
     that is read to its end;
   - a **~300-line chunk sent alone**, defect last, twice (cents): whether
     Option B's premise holds, as ADR-0011's 334-line file suggests.
2. **How to measure** (the probe from the last chat was in a scratchpad and is
   gone): build `SourceFile(path, content)` from text, which skips the workspace
   check; mark with `build_request(source, changed=frozenset(window))`; call
   `OpenAIProvider` built from `load_settings()`; read results with
   `parse_findings`. The file is `.venv/Lib/site-packages/click/core.py` (3,806
   lines, ~44k tokens). The defect is a `summarize_option_lengths` function whose
   last line is an unguarded `total / len(options)`, appended as the last
   function. Commit the probe as `scripts/probe_attention.py` so the ADRs'
   evidence can be re-run by anyone.
3. **Put a cost table in front of the user** - A at the window size that works,
   against B - and get a decision.
4. **Write ADR-0014 superseding ADR-0013**, then build, with tests at the right
   level, then verify live once (asking first).

If the user asks for something else, do that. This is the recommended next
step, not an order that outranks them.

## 4. Rules that bite

- Branch, pull request, CI green on three platforms. **Merging needs the user's
  say-so in this chat**; authorisation from an earlier chat does not carry over.
- **Never call a real provider without asking**, and state the cost first. The
  key is in `.env`: never print, copy, or commit it.
- `uv run python scripts/check.py` before claiming anything is done, and report
  what it said. Chain it with `set -o pipefail`, or a failing gate piped through
  `tail` still lets the next command run.
- Commits: Conventional Commits, a body that says *why*, and the
  `Co-Authored-By` trailer. Pass the message with `-F` or a quoted heredoc.
- Update `status.md` in the same pull request as the work. A test holds it to
  150 lines; prune what is stale rather than raising the number.
- An accepted ADR is superseded, never rewritten. Measurement results and a
  status change may be added to it; the decision text stays.

## 5. Lessons carried forward

Each cost real time once. Keep only what is still true and not already enforced
by a test or written in `status.md`.

- **Run the measurement a decision depends on before asking the user to
  decide.** ADR-0013 was accepted on Option A and suspended hours later by the
  window-size measurement it had deferred. The user was asked the wrong question
  first.
- A Python heredoc containing triple-quoted strings can break bash quoting.
  Write the script to the scratchpad with the Write tool, then run it.
- `gh pr merge --delete-branch` closes any pull request stacked on that branch,
  and it cannot be reopened. Do not stack; or rebase onto `main` and retarget
  before deleting the base.
- `gh pr checks --watch` straight after a push prints "no checks reported" and
  exits. Wait until `gh run list` shows the run.
- `forge` run outside the repository finds no `.env` and exits 3. For a probe
  repository elsewhere, load the key without echoing it:
  `set -a; . D:/code-project/Forge/.env; set +a`.

## 6. The handoff loop

This section keeps the chain of chats alive. **Carry it into every new version
of this file**, and change it only where the chat that is ending found a real
flaw in it. A test fails the build if it disappears.

**When.** Call `get_usage` at the start, after each merged pull request, and
before anything large. **Before starting a task, judge whether it can reach a
clean state before 70%; if it cannot, do its largest step that can - a
measurement, an ADR, a failing test - and hand off.** At **about 70% of the
context window**:

- if a task is in progress, finish it to a clean state - gate green, committed,
  pushed, its pull request merged or clearly left open - then hand off;
- if nothing is in progress, hand off now.

If the percentage cannot be read, hand off early rather than late. If the user
says the chat is at 70%, that is authoritative.

**How.** Rewrite this file, `.forge/NEXT_PROMPT.md`, so that it is *better* than
the version you started from - never a copy carried forward:

1. Increment the generation and update the date.
2. Rebuild section 2 from `git`, `gh` and `get_usage`, never from memory.
3. Replace section 3 with the true next task, including every decision the user
   made in this chat, and anything the next chat would otherwise rediscover -
   a probe, a command, a file path.
4. In section 5, add at most three lessons from this chat - only what cost real
   time and one sentence would have prevented - and delete any lesson that is
   obsolete, now enforced by a test, or already in `status.md`.
5. Answer the improvement check below and act on every "yes".
6. Stay under 200 lines. A test enforces it: compress, do not accrete.

**Improvement check**, against the chat that is ending:

- Did it ask the user anything this file could have answered - or ask before it
  had the evidence the answer depended on?
- Did any instruction here prove wrong, stale, or rightly ignored?
- Did anything cost more than a few minutes that a sentence would have saved?
- Is the new version no longer than the old one while carrying more?

**Then.** Commit it through a pull request together with the `status.md` update,
merging only as section 4 allows. Paste the **complete** new file to the user in
**one** code block, and under it three lines: what changed, why this version is
better, and the context and weekly plan percentages at hand-off.
