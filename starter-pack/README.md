# 🚀 Rasa Mantle Starter Pack

**Build your first Rasa Mantle agent — with training wheels that actually work.**

Hi! If you're new to Rasa Mantle (or new to building AI agents at all),
you're in the right place. This pack gives you three things:

1. **A smart assistant setup** — ready-made instructions that teach Claude
   Code how to build Mantle projects *correctly*, so you can just describe
   what you want.
2. **A safety net** — a small checker program that catches the most common
   Mantle mistakes *before* they waste your afternoon.
3. **An automatic guard** — a one-time setup that runs the checker every
   time you save your work, so mistakes can't sneak in.

You don't need to know what a "linter" or a "git hook" is. We'll explain
everything as we go. 💪

---

## Why does this exist? (30 seconds of honesty)

Rasa Mantle is powerful, but it has a handful of traps that are **silent** —
you make the mistake, nothing complains, and your agent just quietly
misbehaves. For example: put your agent's rules in *slightly* the wrong spot
in a config file, and Mantle reads them, throws them away, and never tells
you. Real projects shipped with 39 rules the engine never applied, and
nobody noticed for weeks.

Every check and every instruction in this pack comes from a **real mistake a
real project actually made**. We stepped on the rakes so you don't have to.

---

## What you need before starting

| Tool | What it is | How to get it |
| --- | --- | --- |
| **Python 3.11 or newer** | The language Mantle runs on | [python.org/downloads](https://www.python.org/downloads/) — check with `python3 --version` |
| **git** | Saves snapshots of your work | Usually pre-installed — check with `git --version` |
| **uv** | Installs Python packages, fast | [docs.astral.sh/uv](https://docs.astral.sh/uv/) — one command to install |
| **Claude Code** | The AI assistant this pack teaches | [claude.com/claude-code](https://claude.com/claude-code) |
| **A Rasa license** | Free for developers | [Request a free Developer Edition key](https://rasa.com/rasa-pro-developer-edition-license-key-request/) |
| **An OpenAI API key** | Powers your agent's brain | [platform.openai.com](https://platform.openai.com/) |

Don't have everything yet? That's fine — you can do steps 1–3 below with
just Python and git, and add the keys when you're ready to run the agent.

---

## Setting up (about 10 minutes)

### Step 1 — Make a folder for your project

Open a terminal and run these lines one at a time:

```bash
mkdir my-agent
cd my-agent
git init
```

`git init` tells git "please track my work in this folder." You only ever
run it once per project.

### Step 2 — Copy the starter pack in

Copy these four things from the starter pack into your new folder:

```bash
cp -R /path/to/starter-pack/CLAUDE.md .
cp -R /path/to/starter-pack/.claude .
cp -R /path/to/starter-pack/scripts .
cp -R /path/to/starter-pack/hooks .
```

(Replace `/path/to/starter-pack` with wherever you downloaded this pack.)

What did you just copy?

- `CLAUDE.md` — the rulebook Claude Code reads automatically when it works
  in your folder.
- `.claude/` — six "skills" (step-by-step playbooks for building Mantle
  pieces) and two "roles" (a builder and a reviewer). Claude Code finds
  these on its own; you don't need to do anything with them.

> ⚠️ **If you also ran `rasa init`, you have twelve skills, not six.** Rasa
> installs six Mantle skills of its own, with names that rhyme with these
> (`mantle-building-skills` vs our `mantle-skill-authoring`, and so on).
> They are not duplicates, but they are not interchangeable either:
> **Rasa's teach the engine contract; ours teach the failure modes of one
> pinned version and hook each to a checker.** Read
> [`.claude/skills/OVERLAP.md`](.claude/skills/OVERLAP.md) — it states, per
> skill, exactly what ours adds over the Rasa one covering the same ground,
> and names four things Rasa's skills cover that this pack does not.
- `scripts/` — the checker program (more on it in a second).
- `hooks/` — the automatic guard (more on it in Step 4).

> 💡 **Heads-up:** `.claude` starts with a dot, which means your file
> browser probably hides it. It's there — `ls -a` in the terminal shows it.

### Step 3 — Try the checker

The checker (`lint_mantle.py`) is a small program that reads your project
files and looks for the known Mantle traps. Programmers call this kind of
tool a **linter** — it "picks the lint off" your code. Run it:

```bash
python3 scripts/lint_mantle.py
```

Right now your project is nearly empty, so you'll see a few findings like
"missing pyproject.toml" — **that's normal and good!** It means the checker
works. Each line tells you exactly what's missing and how to fix it. A fully
set-up project prints:

```
ok — 0 finding(s) across 9 check(s)
```

That's the goal. Green means go.

### Step 4 — Turn on the automatic guard

Now the neat part. Git has a feature called **hooks**: little programs that
run automatically at key moments. We'll install one that runs the checker
every time you *commit* (= save a snapshot of your work):

```bash
./hooks/install-hooks.sh
```

You'll see:

```
Installed: .git/hooks/pre-commit
Every commit now runs: python3 scripts/lint_mantle.py
```

From now on, if you try to save work that contains one of the known traps,
git will stop and show you exactly what's wrong:

```
COMMIT BLOCKED by lint_mantle.py (exit 1).
Each finding above names its fix.
```

This isn't punishment — it's the pack catching a silent bug **now**, while
it's a 30-second fix, instead of **later**, when it's a mystery. Fix what
the message says, then commit again. That's the whole workflow.

> 💡 You only run `install-hooks.sh` once per project. The guard stays on.

**One habit worth forming now: commit the skills too.** The files in
`.claude/skills/` are yours once they're in your folder, and you *should*
edit them when one is wrong — a key that moved, a version that changed, a
trap that bit you. When you do, save it like any other work:

```bash
git add .claude/skills/
git commit -m "skills: note that tool_timeout is top-level as of dev6"
```

Why bother? **Your collaborator inherits your fixes.** Claude Code reads
these files automatically, so a correction you commit doesn't just help the
next human who clones your project — it quietly corrects *their* assistant
too. Left uncommitted, that fix helps exactly one person, and disappears the
next time Rasa updates its own copies of these files.

### Step 5 — Let Claude Code build your agent

Open Claude Code inside your project folder and say something like:

> "Use the **mantle-new-project** skill to scaffold a customer-support agent
> for a small bakery. Call it Poppy."

Claude Code will read the skill (a detailed playbook that knows all the
correct file shapes) and create every file your agent needs. When it's done,
run the checker again — it should say `ok`.

Then bring your agent to life:

```bash
make env        # creates your personal .env file for API keys
# open .env in any editor and paste in your RASA_LICENSE and OPENAI_API_KEY
make install    # downloads Rasa Mantle (takes a few minutes the first time)
make train      # teaches the engine your agent
make chat       # talk to your agent! 🎉
```

---

## Everyday cheat sheet

| You want to… | Run this |
| --- | --- |
| Check your project for traps | `python3 scripts/lint_mantle.py` |
| Check just one thing | `python3 scripts/lint_mantle.py --check nested-if` |
| See all check names | `python3 scripts/lint_mantle.py --list` |
| Add a new skill to your agent | Ask Claude Code to "use the mantle-skill-authoring skill" |
| Change the AI model / provider | Ask for the "mantle-llm-and-integrations skill" |
| Something's broken and weird | Ask for the "mantle-upgrade-and-debug skill" — it has a table mapping error messages to real causes |
| Get your work reviewed | Ask Claude Code to "review this as mantle-reviewer" |
| Know which skill governs (you have 12) | Read `.claude/skills/OVERLAP.md` |
| Keep a fix you made to a skill | `git add .claude/skills/ && git commit` — see below |

---

## When the checker complains — what the messages mean

Every message names its own fix, but here's the plain-English version of
what each check protects you from:

- **agent-top-level-keys** — Your agent's rules are in a spot where Mantle
  *silently ignores them*. Move them where the message says. (This is the
  39-ignored-rules bug. It makes no error sound at all. The checker is the
  only alarm.)
- **llm-model-group** — Your AI-model settings use an old format that new
  Mantle versions reject. Most tutorials on the internet still show the old
  format, so this one bites everyone.
- **project-memory-writes** — A memory field is marked "the AI may write
  this" in a file where that's not allowed. The fix is a one-line move.
- **nested-if** — An `if:` line is indented, so Mantle treats it as plain
  text instead of logic. Your branch never runs. Un-indent it.
- **skill-prose** — You referenced a memory value in a way that won't be
  filled in — the user would literally see `session.project.name` as text.
- **engine-version-pin** — Your project points at a Rasa version that
  doesn't contain the Mantle engine at all. ⚠️ This is the big one:
  **the newest "stable" Rasa has no Mantle inside** — you need a
  `3.20.0.dev` version, even though "dev" sounds scarier than "stable".
- **secret-hygiene** — An API key or password is about to be saved into git
  history (which is very hard to un-do, and public if you ever share the
  repo). Move it into `.env`, which git is told to ignore.
- **env-example** — Your project uses a key that `.env.example` doesn't
  mention, so the next person (or future-you) can't discover they need it.
- **retired-brand** — You used the old product name for the engine.
  Commands with the old name don't just look dated — they *fail*.

---

## FAQ

**Do I have to use the checker? It blocked my commit!**
You can bypass it once with `git commit --no-verify`, but the checker only
speaks up about mistakes that are *silent* at runtime — so bypassing it
usually means shipping a bug you won't see until much later. If you're sure
it's wrong, bypass and say why in your commit message.

**The checker says my Rasa version is wrong, but I picked the newest one!**
That's the trap. The Mantle engine currently ships **only in pre-release
("dev") versions**. The newest stable release literally does not contain the
engine. Pin `rasa-pro==3.20.0.dev6` — the skills do this for you.

**`make install` fails with a confusing message about versions.**
Nine times out of ten this is the Python floor: Mantle needs Python 3.11+,
and the error message doesn't mention Python at all. The
mantle-upgrade-and-debug skill's table covers this and friends.

**Can I use this without Claude Code?**
Yes! The checker and the git hook work on their own. The `.claude/skills/`
files are also just well-organized Markdown — they're a solid Mantle
handbook for humans too.

**Is my API key safe?**
Keys live in `.env`, which is never saved to git, and the checker actively
scans for keys accidentally pasted anywhere else. Just never edit
`.env.example` to contain a *real* value — that file IS saved to git.

---

## Where this all comes from

Assembled 2026-09-02 from `RasaHQ/rasa-community-resources` at rasa-pro
`3.20.0.dev6`. Every rule was distilled from that catalog's shipped
projects and its own checker — each one encodes a failure a real project
actually hit. When Mantle reaches a stable release, the version advice
above is the part to re-check first.

Happy building! 🛠️
