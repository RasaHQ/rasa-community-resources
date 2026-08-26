# Resource README template

Copy this into your resource directory as `README.md`, then replace every
placeholder. Keep the metadata block at the top — the root README and category
catalogs depend on it.

For folder choice, naming, and PR rules, see [CONTRIBUTING.md](../CONTRIBUTING.md).
For the difference between the maintained catalog and frozen wave projects, see
[SNAPSHOTS.md](SNAPSHOTS.md) — it decides which metadata block below you use.

---

## Skeleton

Start your README like this (metadata first, then title and body):

**Metadata block** (plain text, immediately under the H1 or as the first code-style block):

    Author:        Your Name
    Assessed on:   YYYY-MM-DD
    Assessed by:   Name who last verified it runs
    Verified with: rasa-pro X.Y.Z, Python 3.11+, uv
    Audience:      One line — who this is for
    Time:          Honest estimate, e.g. 45 minutes / 75–90 minutes

**Untyped-folder variant** — for `community/` and `heroes/`. Same fields, plus
one that says what the resource is, since neither folder is typed by its path.

`community/` is maintained: pin `RASA_PRO_VERSION` like any other resource.
`heroes/` is frozen: `Verified with:` records the version **you** ran, it does
not have to match the catalog pin, and it will not be bumped for you.

Under `community/`:

    Author:        Your Name
    Kind:          pattern | example | tutorial | workshop | snippet
    Assessed on:   YYYY-MM-DD
    Assessed by:   Name who verified it runs
    Verified with: rasa-pro X.Y.Z, Python 3.11+, uv
    Audience:      One line — who this is for
    Time:          Honest estimate

Under `heroes/<wave>/projects/`:

    Author:        Your Name
    Wave:          wave-NN-<theme>
    Assessed on:   YYYY-MM-DD
    Assessed by:   Name who verified it runs
    Verified with: rasa-pro X.Y.Z, Python 3.11+, uv
    Audience:      One line — who this is for
    Time:          Honest estimate

Either way, commit a `uv.lock` resolving to the version the `Verified with:`
line names. `make validate` checks that the two agree.

**Recording a version you verified in the past** — in a provenance table, a
changelog line, a "what changed" note — write it as a bare backticked number
like `` `3.19.0.dev5` ``. Do not put the words `rasa-pro` immediately before it:
`make migrate` rewrites that form, and a note about what you tested last month
silently becomes a claim about a version you never ran.

**Suggested sections**

1. **Title** — `# <Resource title>`
2. **Metadata block** — as above
3. **Opening** — one or two sentences on what this is and why someone would clone it
4. **How to use it** — e.g. run finished material vs build step by step
5. **Demo identity** — who or what is seeded, if any
6. **What it covers** — table of skills / pieces
7. **Quick start** — install / env / verify / train / inspect (or equivalent)
8. **Required secrets** — env var names only, never values
9. **Architecture** — short diagram or bullets; link to `AGENTS.md` if present
10. **What breaks / caveats** — honest failure modes and version pins
11. **Licence** — point at the repo root `LICENSE` (Apache 2.0 for teaching material; Rasa Pro has its own terms)

---

## After you finish the README

1. Add a row to the index that covers your folder:
   - maintained catalog → `examples/README.md`, `tutorials/README.md`, `patterns/README.md`, …
   - `community/` → [`community/README.md`](../community/README.md)
   - `heroes/` → your **wave charter**, `heroes/<wave>/README.md`
2. Open one pull request for this resource only.
3. Expect review against the standards in [MAINTAINERS.md](../MAINTAINERS.md).
