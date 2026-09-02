# Rasa Heroes

Projects built by participants of the **Rasa Heroes** programme, organised by
the cohort — the *wave* — that built them.

This folder is **accepting waves**. The open cohort is
[**wave-01-mantle**](wave-01-mantle/README.md) — the first cohort on the Mantle
engine — and it is accepting projects now.

A wave is a fixed group of people working over a fixed period on a shared theme.
The point of keeping their work here rather than scattered across forks is that
a cohort's output stays readable as a set: same period, same theme, same Rasa Pro
version, all credited by name.

---

## Layout

```text
heroes/
  README.md                      this page — the index of every wave
  WAVE_TEMPLATE.md               copy this into a new wave's README.md
  wave-01-mantle/                the open cohort
    README.md                    the wave charter: dates, theme, stewards, projects
    projects/
      <participant-handle>-<project-slug>/
        README.md
        pyproject.toml
        uv.lock
        .env.example
        …
```

Wave slugs are `wave-NN-<theme>`, zero-padded, so the directory listing and the
chronological order are the same thing: `wave-01-mantle`, `wave-02-<theme>`,
`wave-10-<theme>`. `make validate` enforces the shape — a project filed
anywhere other than `<wave>/projects/<project>/` is invisible to every check,
which is exactly the failure worth catching at review time rather than a year later.

---

## Wave projects are frozen

A wave project pins the Rasa Pro version its author verified during that wave and
is never migrated forward. `make migrate` skips it, and the repo-wide version
check skips it.

This is the honest arrangement. A cohort finishes; its participants move on; no
one has undertaken to re-verify wave-01's projects against a release shipped two
years later. Freezing says so out loud, with a date and a name attached, instead
of letting the material rot quietly behind a green build.

What *is* enforced: a real `uv.lock`, a `Verified with:` line matching the pin,
an author, an assessment date, the wave it belongs to, and a `.env.example` with
no secrets in it. Full contract: [`docs/SNAPSHOTS.md`](../docs/SNAPSHOTS.md).

---

## Waves

| Wave | Theme | Period | Participants | Charter |
|---|---|---|---|---|
| `wave-01-mantle` | First cohort on the Mantle engine | TBD | TBD | [charter](wave-01-mantle/README.md) |

_One wave, open. `wave-01-mantle` has its period, stewards and roster marked TBD
until the programme announces them — they are not estimated here._

---

## Starting a wave

For programme stewards.

1. `mkdir -p heroes/wave-NN-<theme>/projects`
2. Copy [`WAVE_TEMPLATE.md`](WAVE_TEMPLATE.md) to `heroes/wave-NN-<theme>/README.md`
   and fill in the charter: dates, theme, stewards, and the participant roster.
3. Add the wave's row to the table above. `make validate` fails a wave that the
   programme index does not list.
4. Open one pull request for the wave charter, before any project lands.

## Landing a project in a wave

For participants.

1. Create `heroes/wave-NN-<theme>/projects/<your-handle>-<project-slug>/`.
2. Start from [docs/RESOURCE_TEMPLATE.md](../docs/RESOURCE_TEMPLATE.md), using
   the **frozen snapshot** metadata block, and set `Wave: wave-NN-<theme>`.
3. Commit a `uv.lock`. Your project pins whatever Rasa Pro version you verified
   against — it does not have to match `RASA_PRO_VERSION`, and it will not be
   bumped for you.
4. Add your project's row to your **wave charter** (`<wave>/README.md`), not to
   this page. This page indexes waves; a wave indexes its projects.
5. Run `make validate` from the repository root, then open one pull request for
   your project alone.

Your name stays on your project. See the attribution policy in
[MAINTAINERS.md](../MAINTAINERS.md).
