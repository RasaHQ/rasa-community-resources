# Wave 01 — First cohort on the Mantle engine

```text
Wave:          wave-01-mantle
Period:        TBD — not yet announced
Stewards:      TBD — not yet announced
Rasa Pro:      3.20.0.dev6 — the version this cohort built against
Participants:  TBD — roster not yet final
```

The first Rasa Heroes cohort, and the first group to build on the **Mantle**
engine rather than on the CALM-era stack that preceded it. The wave exists
because Mantle changed what a Rasa project looks like from the first command
onwards, and no amount of reference documentation substitutes for a set of real
projects, built independently, by people meeting the engine for the first time.
What this cohort produces is therefore a record of where a newcomer to Mantle
actually gets stuck — which is the thing the documentation cannot tell us about
itself.

This charter is **open and accepting projects.** Submissions land by
**2026-09-20.** The period, the stewards and the participant roster are marked
TBD above because they are not settled yet; they are filled in here, not
guessed at, once the programme announces them. Nothing below has been
back-dated or estimated.

## Theme

**In scope:** anything built on the Mantle engine at `rasa-pro 3.20.0.dev6` —
voice or text, a full agent or a single pattern worth reusing. The shared
constraint is the engine and the pin, not the domain.

**Explicitly not in scope:** projects built on the CALM-era stack, and projects
that cannot be reproduced from what is committed. A wave project is a frozen,
dated record, so it has to run from its own `uv.lock` and its own
`.env.example` without private setup.

## Participants

The roster is not final. Each participant adds their own row here in the same
pull request that adds their project.

| Participant | GitHub | Project |
|---|---|---|
| _TBD — roster not yet announced_ | — | — |

## Projects

No projects have landed yet. This wave is open.

| Project | What it does | Author | Verified with | Assessed on |
|---|---|---|---|---|
| _none yet_ | — | — | — | — |

Every project directory under `projects/` must appear in this table — the build
fails otherwise, because an unlisted project is one nobody can find. Adding a
directory and adding its row here are one pull request, never two.

## What this cohort found

Not yet written. This section is filled in when the wave closes, not while it
is running — a findings list assembled in advance is a plan, not a finding.

It should end up as three to six specific bullets: what worked, what did not,
what surprised people, and what the next wave should not repeat. A wave that
learned something negative is more useful than one that reports only successes.

## Frozen

These projects are pinned to `rasa-pro 3.20.0.dev6` and are not migrated
forward. See [`docs/SNAPSHOTS.md`](../../docs/SNAPSHOTS.md) for what that
guarantees and what it does not.
