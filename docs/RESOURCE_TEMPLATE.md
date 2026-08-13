# Resource README template

Copy this into your resource directory as `README.md`, then replace every
placeholder. Keep the metadata block at the top — the root README and category
catalogs depend on it.

For folder choice, naming, and PR rules, see [CONTRIBUTING.md](../CONTRIBUTING.md).

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

1. Add a row to the category catalog (`examples/README.md`, `tutorials/README.md`, etc.).
2. Open one pull request for this resource only.
3. Expect review against the standards in [MAINTAINERS.md](../MAINTAINERS.md).
