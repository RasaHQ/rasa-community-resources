# Community

Resources written by practitioners in the community, credited to their authors
and maintained on the same Rasa Pro pin as everything else here.

---

## How this differs from the category folders

Not by quality, and not by maintenance. A resource here moves with
[`RASA_PRO_VERSION`](../RASA_PRO_VERSION) exactly like one in
[`patterns/`](../patterns/) or [`examples/`](../examples/): `make migrate`
rewrites it, `make check-all` proves it still runs, and it is expected to stay
green. An example pinned to a release the rest of the catalog has moved off is
one nobody clones — being current is most of what makes a contributed resource
worth checking in.

What differs is **ownership**. The category folders hold material an area owner
has undertaken to shepherd, and `patterns/` in particular is meant to be the
canonical treatment of its problem. This folder is where good contributed work
lands without anyone having to claim that status for it, or claim a
maintainership slot to get it merged.

You do not sign up for anything by contributing here. Migration is the
maintainers' job. When a maintainer bumps your resource forward they re-run it
and put **their** name on `Assessed by:` — never yours on a version you did not
test. `Author:` is yours permanently. See
[`docs/SNAPSHOTS.md`](../docs/SNAPSHOTS.md) for the two tiers and
[MAINTAINERS.md](../MAINTAINERS.md) for the attribution policy.

If a resource here cannot be brought forward — it needs a provider key nobody
has, or it simply stops working — it is archived with the reason, rather than
left on a stale pin implying it still runs.

---

## What belongs here

- A resource you wrote, that runs, that you want credited to you
- Anything the category folders would take, where you would rather not also
  argue that it is the canonical answer
- A working configuration that is specific rather than general — a provider
  swap, a deployment shape, an integration

## What does not belong here

| Instead… | When… |
|---|---|
| [`patterns/`](../patterns/) etc. | It is the canonical treatment of the problem and someone will own the area |
| [`heroes/`](../heroes/) | It is a Rasa Heroes wave deliverable. It belongs to its cohort, and is frozen at that cohort's pin |
| [community showcase](https://rasa.community/showcase/) | It is a product or a demo of your company's work, not teaching material |

---

## Naming

```text
<github-handle>-<resource-slug>
```

Example: `samrudh-gemini-voice-agent`.

The handle prefix is not decoration. This folder is flat and contributor-owned,
so the prefix makes ownership visible in the tree, keeps `git log` readable, and
means two people can solve the same problem without fighting over a slug.

Each resource is one directory with its own `README.md`, `pyproject.toml`,
`uv.lock`, and `.env.example`.

---

## Catalog

| Name | Kind | Summary | Author | Assessed on |
|---|---|---|---|---|
| [`samrudh-gemini-voice-agent`](samrudh-gemini-voice-agent) | example | Atlas voice travel agent on Google Gemini, with local sentence-transformers embeddings — no OpenAI key anywhere | Samrudha Kelkar | 2026-08-26 |

---

## How to add one

1. Read [CONTRIBUTING.md](../CONTRIBUTING.md).
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md) and add
   the `Kind:` field — this folder is flat, so the metadata says what the
   resource is.
3. Pin `rasa-pro` to [`RASA_PRO_VERSION`](../RASA_PRO_VERSION) and commit a
   `uv.lock`.
4. If your resource needs a provider key beyond `RASA_LICENSE`,
   `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`, declare it so a runner without the
   key skips training instead of failing:

   ```toml
   [tool.rasa-catalog]
   required-secrets = ["GEMINI_API_KEY"]
   ```

   It must appear in your `.env.example` too — `make validate` checks that.
5. Add your row to the catalog above **in the same pull request**. An unlisted
   directory is invisible, and the build fails for it.
6. Run `make validate`, then `make check-all` if you changed anything runnable.

Review ownership and response times: [MAINTAINERS.md](../MAINTAINERS.md).
