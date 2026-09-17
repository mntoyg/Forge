# Forge - the prompt that starts the next chat

Generation 1 · written 2026-09-17 · by the chat that accepted ADR-0013.
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
3. `.forge/context/decisions.md`, then the ADR the task below names.
4. Check reality before trusting any snapshot: `git fetch`,
   `git log --oneline -5 origin/main`, `gh pr list`, and
   `gh repo view mntoyg/Forge --json visibility`.
5. Load `mcp__ccd_session_mgmt__get_usage` with ToolSearch and call it. Tell the
   user the context percentage and the weekly plan percentage before any large
   task - the weekly plan is shared by every chat.

## 2. The snapshot this prompt was written against

- `main` includes ADR-0013 (accepted, not implemented) and this file. CI runs
  on ubuntu, macOS and Windows, and was green.
- `0.1.0` is prepared and **not tagged**, and the repository is **private**.
  Both are the user's calls; do neither unasked.
- `mntoyg/Forge-archive` holds the old history and pull requests #1-#15, and it
  carries the user's personal email address. **It must never be made public.**
- Weekly plan usage was 83% on 2026-09-17, resetting 2026-09-19.

## 3. The task

**Implement ADR-0013: review a long file as a series of marked windows.** The
user decided: Option A - the whole file on every call with one window of lines
marked, never split content - and `FORGE_MAX_REVIEW_CALLS` defaulting to 8.

1. **Measure the window size first.** Ask before spending, and say the cost
   (1-3 US cents). Mark a 300-line and an 800-line window in a file of about
   44,000 tokens, with the defect on the window's last line, and run each at
   least twice. Record the result in ADR-0013 and `status.md`.
2. **State the plan before writing code**: which layer each piece lives in and
   which tests prove it. Windowing is application-layer; the setting belongs in
   `infrastructure/config.py`; the caveat lives in `cli/debug.py`; the marked
   prompt path already exists in `application/prompt.py`.
3. **Build it with tests at the right level**, then verify live once on a file
   that needs windowing - asking first.
4. Pull request, CI green on all three platforms, merge only as section 4 allows.

If the user asks for something else, do that. This is the recommended next
step, not an order that outranks them.

## 4. Rules that bite

- Branch, pull request, CI green on three platforms. **Merging needs the user's
  say-so in this chat**; authorisation from an earlier chat does not carry over.
- **Never call a real provider without asking**, and state the cost first. The
  key is in `.env`: never print, copy, or commit it.
- `uv run python scripts/check.py` before claiming anything is done, and report
  what it actually said.
- Commits: Conventional Commits, a body that says *why*, and the
  `Co-Authored-By` trailer. Pass the message with `-F` or a quoted heredoc -
  backticks inside `-m "..."` are eaten by the shell.
- Update `status.md` in the same pull request as the work. A test holds it to
  150 lines; prune what is stale rather than raising the number.
- Measure before asserting. Every live result that changed a decision here was
  run at least twice, because temperature 0 is not determinism.

## 5. Lessons carried forward

Each cost real time once. Keep only what is still true and not already enforced
by a test or written in `status.md`.

- A Python heredoc containing triple-quoted strings can break bash quoting.
  Write the patch script to the scratchpad with the Write tool, then run it.
- `gh pr merge --delete-branch` closes any pull request stacked on that branch,
  and it cannot be reopened. Rebase the stacked branch onto `main` and retarget
  it before deleting its base.
- `gh pr checks --watch` straight after a push prints "no checks reported" and
  exits. Wait until `gh run list` shows the run.
- A release number is not a tag: `astral-sh/setup-uv` publishes `v10.0.1` but
  no moving `v10`. Check `gh api repos/OWNER/REPO/git/ref/tags/TAG` before
  bumping an action.
- The sandbox refuses `git filter-branch`; `uvx --from git-filter-repo
  git-filter-repo --mailmap FILE` does the same job.
- `forge` run outside the repository finds no `.env` and exits 3. For a probe
  repository elsewhere, load the key without echoing it:
  `set -a; . D:/code-project/Forge/.env; set +a`.

## 6. The handoff loop

This section keeps the chain of chats alive. **Carry it into every new version
of this file**, and change it only where the chat that is ending found a real
flaw in it. A test fails the build if it disappears.

**When.** Call `get_usage` at the start, after each merged pull request, and
before anything large. At **about 70% of the context window**:

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
   made in this chat, so the next chat does not ask again.
4. In section 5, add at most three lessons from this chat - only what cost real
   time and one sentence would have prevented - and delete any lesson that is
   obsolete, now enforced by a test, or already in `status.md`.
5. Answer the improvement check below and act on every "yes".
6. Stay under 200 lines. A test enforces it: compress, do not accrete.

**Improvement check**, against the chat that is ending:

- Did it ask the user anything this file could have answered?
- Did any instruction here prove wrong, stale, or rightly ignored?
- Did anything cost more than a few minutes that a sentence would have saved?
- Is the new version no longer than the old one while carrying more?

**Then.** Commit it through a pull request together with the `status.md` update,
merging only as section 4 allows. Paste the **complete** new file to the user in
**one** code block, and under it three lines: what changed, why this version is
better, and the context and weekly plan percentages at hand-off.
