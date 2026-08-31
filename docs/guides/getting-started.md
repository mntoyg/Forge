# Getting Started

Install Forge, point it at a file, and read what comes back.

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

## 2. Configure

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

## 3. Analyse a file

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

## 4. Read the output

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

The footer names the model that answered and what the call cost. Both are
there because you paid for it, and because "which model said this" is the first
question worth asking about a surprising finding.

## 5. Use it in a script

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
