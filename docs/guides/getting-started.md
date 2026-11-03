# Getting Started

Install Forge, inspect a project locally, then point it at a file and read
what comes back.

Takes about five minutes, and you need an API key from an OpenAI-compatible
provider. Forge uses **your** key and calls **your** account - there is no
hosted service in between, and no free tier to run out of.

## 1. Install

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). It
installs Python 3.13 for you.

```bash
git clone https://github.com/mntoyg/Forge.git
cd Forge
uv sync --all-groups
```

Check it worked:

```bash
uv run forge --version
```

```text
forge 0.0.1
```

That command needs no key. If it works, the install is fine.

## 2. Inspect a project

Before configuring a provider, get a local overview of the repository:

```bash
uv run forge inspect
```

The report identifies guidance files, languages inferred from file extensions,
recognized project tooling, available checks, and a shallow directory outline.
It cites the paths behind each fact, and calls out missing evidence or scan
limits. It reads only selected project metadata, skips symlinks, paths matched
by project `.gitignore` rules, sensitive files, virtual environments, generated
output, and known binary types, and never prints guidance contents or executes
repository commands. It does not need an API key.
Git info and global exclude rules are outside the scan.

## 3. Configure

```bash
cp .env.example .env
```

Open `.env` and set your key:

```bash
FORGE_API_KEY=your-key-here
```

That is the only required value. Everything else has a sensible default; the
full list with explanations is in `.env.example`.

**`.env` is git-ignored, and it should stay that way.** Forge never prints your
key: it is held as a secret value that survives no log line, no error message,
and no debug output. If a key is ever committed anywhere, treat it as
compromised and rotate it - removing it from history is necessary but not
sufficient, because it already exists in every clone.

### Using a different model or endpoint

```bash
FORGE_MODEL=gpt-4o                       # any model your key can reach
FORGE_BASE_URL=http://localhost:8000/v1  # any OpenAI-compatible server
```

The second line is why Forge works against a self-hosted model as well as a
hosted one. Nothing in the tool is specific to one provider.

## 4. Analyse a file

The repository ships a deliberately broken example:

```bash
uv run forge debug examples/buggy_division.py
```

```text
buggy_division.py: 2 findings

  Severity   Line   Finding
  HIGH         16   Divides by len(values) without guarding an empty list
                    average([]) raises ZeroDivisionError.
                    confidence: certain
  MEDIUM       20   Off-by-one in the slice bound
                    last_n(values, 3) returns two items, not three.
                    confidence: likely

model: gpt-4o-mini-2024-07-18 | tokens: 412 in, 186 out
```

Then try it on something of your own:

```bash
uv run forge debug src/whatever.py
```

### Explain an unfamiliar file

To get an overview rather than a defect analysis, ask Forge to explain one
source file:

```bash
uv run forge explain src/app.py
```

Forge sends the selected file to your configured provider in one request at
most. Each substantive claim cites validated one-based line ranges, with
excerpts taken from the submitted snapshot. Claims without valid evidence are
omitted and the output is marked incomplete. Forge does not inspect adjacent
files, run repository commands, or modify files. A file over the configured
`FORGE_MAX_FILE_BYTES` limit is refused without truncation. Use `--plain` to
disable the progress spinner.

## 5. Read the output

Each finding carries two separate judgements, and conflating them is the most
common way to misread the report.

**Severity** is how much it matters *if the finding is correct*:

| | |
| --- | --- |
| `HIGH` | Fails at runtime, loses data, or exposes something it should not |
| `MEDIUM` | Wrong under conditions that will occur, or a latent bug |
| `LOW` | Clarity, maintainability, or a risk needing unusual conditions |

**Confidence** is how sure the model is:

| | |
| --- | --- |
| `certain` | Provable from the code alone |
| `likely` | Very probably true, but depends on how the code is called |
| `possible` | Worth a look; may be intentional |

A `HIGH` / `possible` finding and a `LOW` / `certain` one need different
reactions. The first is worth checking carefully; the second is worth fixing
when you are next in the file.

Findings are printed most serious first, then most confident first.

Some findings have no line number. That is deliberate: "this module has no
error handling anywhere" is a real observation with no single location, and
inventing one would send you to the wrong place. The same rule applies when the
model cites a line that does not exist in your file - Forge drops the location
rather than guessing a nearby one.

### When the answer may be partial

On a file above roughly 4,000 input tokens, the run ends with a line like this
on stderr:

```text
forge: core.py sent 44,221 tokens. Above roughly 4,000 the model has been seen
to stop reporting defects near the end of a file, so read this as an opinion on
the start of core.py rather than on all of it.
```

You will not see it on a `--diff` run. Marking the changed lines carries the
model's attention to them wherever they sit in the file, which has been
measured: the same defect a whole-file review misses at the end of a 3,807-line
file is found there by `--diff`. On a long file that you are reviewing a change
in, `--diff` is the better command for a reason that is now more than
stylistic.

It is not an error, and the findings above it are still findings. It is there
because the failure it warns about is silent: the model reads the beginning of
a long file and stops, and `no findings` is exactly what a clean file returns.
The measurement behind the number, and why the number is the last size that
*worked* rather than the first that failed, is in
[ADR-0011](../architecture/decisions/0011-warn-when-a-result-may-be-partial.md).

Until Forge reviews a long file in sections, the practical answer is to point
it at the part you care about - a single module rather than a whole file of
them.

### What git adds

Inside a repository, a finding that cites a line carries one more line, and it
is the only part of the report the model had no hand in:

```text
    history: last changed 2026-07-04 by A U Thor (a1b2c3d)
```

The header gains a count in the same spirit - `app.py: 2 findings (4 commits
in the last 90 days)` - because a line last touched a year ago in a file nobody
edits is a different risk from the same line in a file that changed nine times
this quarter.

Two things worth knowing about it:

- A line you have edited but not committed says `not committed yet`. Git can
  name no commit for it, and naming the previous author would blame them for
  your unsaved work.
- Outside a repository, or for a file git has never seen, the line is simply
  absent. History is context around the answer, never a condition for getting
  one - see [ADR-0009](../architecture/decisions/0009-history-annotates-the-answer.md).

None of this is sent to the model. It costs no tokens, and it cannot be wrong
in the way a finding can.

The footer names the model that answered and what the call cost. Both are
there because you paid for it, and because "which model said this" is the first
question worth asking about a surprising finding.

## 6. Review just what you changed

Before committing, you usually want an opinion on the lines you just wrote -
not on the whole file:

```bash
uv run forge debug src/app.py --diff
```

Only lines changed since the last commit are reviewed. Staged and unstaged
count, and a file you have just created counts entirely as new.

The whole file is still sent to the model, because a change cannot be judged
without the code around it: `- if x > 0:` becoming `+ if x >= 0:` is either a
fix or a bug, and nothing in those two lines says which. So `--diff` narrows
the **answer**, not the bill - input cost is similar, output is smaller, and
what you read is only about your change.

Two things stop it working, and both say so plainly:

```text
forge: app.py has no uncommitted changes. Drop --diff to analyse the whole file.
forge: ... is not inside a git repository, so there is no change to compare
against. Drop --diff to analyse the whole file.
```

Both exit `2`. Everything else about `forge debug` works fine outside git.

## 7. Review the current changes

`forge debug --diff` is for one file. To review multiple changed files in one
request, run:

```bash
uv run forge review
```

This plans a review of staged and unstaged tracked changes plus non-ignored
untracked files. Pass one or more paths to narrow the scope:

```bash
uv run forge review src tests
```

Forge prints included and omitted paths, the configured model, request size,
and an approximate token count. In an interactive terminal, it asks before
sending source to the configured provider. Declining makes no call. Without a
terminal, it prints the plan and makes no call. Each run makes at most one
provider call; the request is limited to 16,000 UTF-8 bytes and is never split
or truncated. If it is too large, narrow the paths and try again.

Known sensitive paths or recognized secret patterns stop the review before
submission. Secret detection is heuristic and cannot find every secret.
Deleted-only files, binary files, symlinks, ignored untracked files, and other
unsupported inputs are shown as omissions. Findings cite a changed line in
the submitted current snapshot, with evidence taken from that snapshot. The
model can still miss defects; submitted files are not guaranteed to have been
fully reviewed. Forge never changes files, runs project commands, or continues
autonomously.

## 8. Use it in a script

Findings do **not** change the exit code:

```bash
uv run forge debug app.py
echo $?    # 0, even with twenty findings
```

This surprises people arriving from linters, so it is worth being explicit: a
linter asserts a standard and should fail your build. Forge reports an opinion
from a language model, and an opinion is not a gate. Exit codes tell you
whether *Forge* worked, not whether your code is good.

| Code | Meaning | What to do |
| --- | --- | --- |
| 0 | Analysis completed | Read the findings |
| 1 | Ran, but produced no usable result | Retry; report it if it persists |
| 2 | Unusable input | Check the path, size, and encoding |
| 3 | Not configured | Set `FORGE_API_KEY` |
| 4 | Provider failed | Wait and retry, or check your key and quota |

So a CI step can react to each cause without parsing any text:

```bash
uv run forge debug app.py
case $? in
  0) ;;                                    # fine, findings or not
  4) echo "provider trouble; retrying"; sleep 30; uv run forge debug app.py ;;
  *) echo "forge could not run"; exit 1 ;;
esac
```

Output drops to plain text automatically when stdout is not a terminal, so a
pipe or a CI log stays readable. `--plain` forces it:

```bash
uv run forge debug app.py --plain > report.txt
```

Results go to stdout and errors to stderr, so `forge debug app.py 2>/dev/null`
gives you only the report.

## What Forge will not do

Worth knowing before you rely on it:

- **It never modifies your files.** It proposes; you decide.
- **It never runs the code it reads.**
- **It only reads inside your working directory.** A path resolving outside is
  refused - including through a symlink. Forge sends what it reads to a third
  party, so that boundary is deliberate.
- **It reads one file at a time.** It cannot see the rest of your codebase, so
  it will not know that the caller three modules away already guards the case
  it is worried about.
- **It can be wrong.** It is a language model reading a file. The confidence
  field is there because that is the honest thing to show.

## When something goes wrong

**`No API key configured`** - exit 3. Set `FORGE_API_KEY` in `.env` or in your
environment.

**`resolves outside the workspace`** - exit 2. Run Forge from the directory
containing the file, or give a path inside it.

**`is N bytes, over the M byte limit`** - exit 2. Forge refuses a large file
rather than analysing part of it, because a report on half a file is confident
nonsense about the half it never saw. Raise the limit if you mean it:

```bash
FORGE_MAX_FILE_BYTES=500000
```

**`is not UTF-8 text`** - exit 2. It is a binary, or an unusual encoding.

**`did not respond in time`** - exit 4. Raise `FORGE_TIMEOUT_SECONDS`, or try a
smaller file.

**The reply could not be parsed** - exit 1. The model did not answer in the
requested format. Retrying usually works; if it happens consistently with a
particular model, that is worth reporting as an issue.

## Next

- [Vision](../product/vision.md) - what Forge is for, and what it deliberately is not
- [Roadmap](../../ROADMAP.md) - what is coming
- [Contributing](../../CONTRIBUTING.md) - how to help
