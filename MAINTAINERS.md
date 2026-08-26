# Maintainers

This document names who is responsible for this repository, what they review, how quickly you can expect an answer, and how attribution works. It exists so that contributors know who they are talking to and so that nothing here becomes orphaned without anyone noticing.

---

## Lead maintainer

**Rod Rivera** — [profrod.ai](https://profrod.ai/) · [@rodriveracom](https://github.com/rodriveracom) · [LinkedIn](https://www.linkedin.com/in/profrodai/)

Developer Relations Engineer at Rasa. Professor of the Practice at ITAM and lecturer at Nebius Academy. Fifteen years of industrial machine learning across Rocket Internet, Samsung NEXT, Alibaba, Huawei, and Philip Morris International, and doctoral studies from Skoltech with 10+ first-author papers at IEEE venues on time series, topological data analysis, and graph neural networks.

He writes and teaches on harness engineering — the practice of building and operating long-running agents — at [profrod.ai](https://profrod.ai/).

**Owns:** editorial direction, the structure of the repository and review queue.

---

## Area owners

Area owners review contributions in their area and are credited on the resources they maintain. To become one, contribute two accepted resources in the same area and open an issue proposing yourself.

| Area | Path | Tier | Owner |
|---|---|---|---|
| Tutorials | `tutorials/` | maintained | Rod Rivera |
| Example projects | `examples/` | maintained | Rod Rivera |
| Patterns | `patterns/` | maintained | Rod Rivera |
| Workshops | `workshops/` | maintained | Rod Rivera |
| Snippets | `snippets/` | maintained | Rod Rivera |
| Community contributions | `community/` | maintained | Rod Rivera |
| Rasa Heroes | `heroes/` | frozen | Rod Rivera |

The table is deliberately honest about the current state: one maintainer, and vacancies waiting to be filled. It will be updated as area owners join.

**Tier** is what the owner is signing up for. Owning a maintained area means
migrating it on every Rasa Pro bump and keeping it green — `community/`
included, because a contributed example on a stale pin is one nobody clones.
Owning the frozen area means reviewing what lands, keeping the index accurate,
and making archive calls — not keeping past cohorts' projects running. See
[`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md).

### Wave stewards

Each Rasa Heroes wave has one or two stewards, named in that wave's charter
(`heroes/<wave>/README.md`). A steward opens the wave, reviews its participants'
projects, and writes the "what this cohort found" section when the wave closes.
Stewardship ends with the wave; the area owner for `heroes/` carries the folder
afterwards.

| Wave | Period | Stewards |
|---|---|---|
| — | — | — |

_No waves yet. Starting one: [heroes/README.md](heroes/README.md)._

---

## Response expectations

These are commitments, not aspirations. If a commitment is missed, it is a bug in the process and worth saying so in the thread.

| Event | Response |
|---|---|
| New issue | Acknowledged within 5 working days |
| New pull request | First review within 10 working days |
| Broken resource reported (something no longer runs) | Triaged within 5 working days; treated as higher priority than new material |
| Security concern | Do not open a public issue — follow the process below |

Reviews are done in batches rather than continuously. A slower first response with a substantive review is preferred over a fast acknowledgement that says nothing.

---

## Rasa Pro version bumps

The catalog pin is [`RASA_PRO_VERSION`](RASA_PRO_VERSION). To roll every
**maintained** resource forward: `make migrate` (or `make migrate VERSION=…`),
then `make check-all` (and `make test-all` when licenses are available).
Details: [docs/MIGRATING.md](docs/MIGRATING.md). After accepting a new resource,
run `make status` so its pin cannot drift from the catalog.

`community/` is part of every bump. What is **not** automatic is the claim:
after migrating a contributed resource, re-run it and set `Assessed by:` to
yourself with today's date. Leaving the author's name on a version they never
tested is the failure mode this whole arrangement exists to avoid. `Author:`
never changes.

Watch for provenance notes while you do it. `make migrate` rewrites any
`rasa-pro <version>` string it finds, including one inside a table recording
what somebody verified last year — it has already done exactly that here once.
Historical versions belong in prose as a bare backticked number.

Frozen wave projects under `heroes/` are not part of a bump. The migrator skips
them and says how many it left alone; `make check-snapshots` proves they still
install at the pins they carry.

---

## Review standards

A contribution is accepted when all of the following hold.

1. **It runs.** Verified against stated versions on a clean environment, with the verification date recorded in the resource README.
2. **It is written for a practitioner.** No talking down, no over-explained basics, no skipped failure modes.
3. **It states what breaks.** Any operational resource includes the conditions under which it fails and what to do about them.
4. **It is honest about time.** If the tutorial takes ninety minutes, it says ninety minutes.
5. **It attributes its sources.** Named practitioners are credited, with permission where the work is theirs. Quotation from external sources is kept minimal and always attributed.
6. **It is engine- and vendor-honest.** Comparisons with other frameworks are welcome when they are fair and specific. Marketing copy is not.

Contributions that are technically sound but out of scope will be declined with an explanation and, where possible, a suggestion of a better home. A declined contribution is not a closed door.

---

## Attribution policy

- Every resource README names its author or authors. Contributors are named on the material they wrote and stay named on it.
- A Rasa Heroes project stays credited to its participant, and stays in its wave, after the wave closes and after the participant moves on.
- Substantive edits add a co-author line rather than replacing the original one.
- The `Assessed on` line records who last verified the resource, which may be someone other than the author.
- Nobody's name is removed from work they did, including after they leave the community.

---

## Security

Do not report security issues in public issues or pull requests. Follow [SECURITY.md](SECURITY.md), which points to the disclosure process at [rasa.com/security-at-rasa/](https://rasa.com/security-at-rasa/).

---

## Succession

If the lead maintainer becomes unavailable, ownership of this repository sits with Rasa's Developer Relations function, and the area owner table above is the list of people to contact first. Any **maintained** resource that has gone unverified for twelve months is moved to `archive/` with a note explaining why, rather than left in place implying it still works.

Frozen snapshots are not archived on a timer — a wave project is *supposed* to
read as a dated artefact, and its `Verified with:` line already says so. They
are archived when they can no longer be made to run at the pin they carry, or
when their author asks. Either way the name stays on the work: credit is
permanent, the implication that something still works is not. The full policy is
in [`docs/SNAPSHOTS.md`](docs/SNAPSHOTS.md).