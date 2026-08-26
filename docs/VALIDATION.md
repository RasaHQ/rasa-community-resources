# Validating the catalog

Everything in this repository is meant to be verifiable by running a command,
not by reading it. This page describes what is checked, by which layer, and how
to fix each failure.

## The three layers

Cheapest first. Each is independently runnable, and each is a strict superset of
the confidence the one above it gives you.

| Command | Time | Needs | Answers |
|---|---|---|---|
| `make validate` | ~2s | `python3` only | Is the repository internally consistent? |
| `make ci` | minutes | + `uv`, network | Does every resource actually install and validate? |
| `make validate-full` | minutes | + `RASA_LICENSE` | Does every resource train end to end? |

```bash
make validate        # run this before every commit
make ci              # run this before merging a resource change
make validate-full   # run this before announcing a version bump
```

`make validate` deliberately installs nothing. That is what keeps it fast enough
to run on every save, and it is why it can run on a clean clone with no
credentials and no network.

### Two tiers

Checks apply to one tier, the other, or both. The **maintained catalog**
(`examples/`, `tutorials/`, `patterns/`, `community/`) is held to the shared pin
in `RASA_PRO_VERSION`. **Frozen snapshots** — only `heroes/` wave projects — are
held to their own pins instead; see [`SNAPSHOTS.md`](SNAPSHOTS.md) for why. The
table below says which is which.

### Useful flags

```bash
make validate STRICT=1            # warnings become failures
make check-all KEEP_GOING=1       # report every failing project, not just the first
make lint                         # lint only
make test-scripts                 # tooling unit tests only
make outdated                     # is there a newer usable rasa-pro? (network)

python scripts/lint_repo.py --json            # machine-readable findings
python scripts/lint_repo.py --list            # check names
python scripts/lint_repo.py --check skill-prose --check lock-sync
```

```bash
make snapshots                    # what is frozen, and at which pin
make check-snapshots              # install each frozen resource at its own pin
python scripts/lint_repo.py --check snapshot-pin --check snapshot-index
```

Exit codes: `0` clean, `1` findings, `2` bad invocation. `--json` emits
`{expected, projects, snapshots, checks, errors, warnings, findings[]}` where
each finding carries `check`, `path`, `line`, `message`, and `severity`.

## What `make validate` enforces

Every check below exists because the failure it describes actually happened here.

| Check | Tier | Enforces | Typical fix |
|---|---|---|---|
| `version-consistency` | catalog | Every `rasa-pro==…` / `Verified with:` string in committed prose matches `RASA_PRO_VERSION` | `make migrate` |
| `version-line` | catalog | The pin stays on the release line that carries the Mantle engine | Pin from `RASA_PRO_VERSION_LINE`; see [MIGRATING](MIGRATING.md) |
| `lock-sync` | catalog | Each `pyproject.toml` pin and `uv.lock` resolve to the pinned version | `make migrate` |
| `prerelease-consistency` | catalog | `[tool.uv] prerelease` and every documented `uv sync` command match whether the pin is a prerelease | `make migrate` |
| `lock-prereleases` | catalog | A **stable** pin carries no leftover prerelease dependencies (warning) | `python scripts/migrate_rasa_pro.py --upgrade` |
| `skill-prose` | both | No raw `session.<ns>.<entry>` and no partial `@memory` token in instruction prose | Use `@memory.<ns>.<entry>`, or a top-level `if:` |
| `nested-if` | both | No indented `if:` — it is only a condition at the top level of a skill body | Move the branch to the top level, or phrase it in natural language |
| `resource-metadata` | both | Each resource README carries `Author` / `Assessed on` / `Assessed by` / `Verified with`, with a sane date — plus `Kind:` under `community/` and `Wave:` under `heroes/` | Fill in the metadata block |
| `secret-hygiene` | both | No tracked `.env`, no committed API keys or licence JWTs | Remove the secret, rotate it, keep it in `.env` |
| `workflow-pins` | repo | Every GitHub Action pinned to a full 40-character commit SHA | See below |
| `agent-config-keys` | both | `rules` / `references` / `name` / `description` / `prompts` / `conversation` / `before_end` sit at the top level of `agent.yml`, not inside `agent:` | Move the key out of the `agent:` block |
| `env-example` | both | Each resource ships `.env.example`, and it names every key the resource declares in `[tool.rasa-catalog] required-secrets` | Add the file or the missing key |
| `snapshot-pin` | frozen | A wave project's `pyproject.toml`, `uv.lock`, and README `Verified with:` all name the same version — and a lock exists at all | `uv lock` in the resource, then make the three agree |
| `index-rows` | both | The resource is listed in `community/README.md` or in its wave charter | Add the catalog row |
| `heroes-layout` | frozen | Wave slugs are `wave-NN-<theme>`; every project sits at `<wave>/projects/<project>/`; every wave is listed in `heroes/README.md` | Rename or move; add the wave row |

### Pinning GitHub Actions

RasaHQ enforces SHA-pinned actions org-wide. An unpinned `uses:` fails the run
before a single step executes, with:

```
Error: The actions actions/checkout@v4 ... are not allowed in
RasaHQ/rasa-community-resources because all actions must be pinned to a
full-length commit SHA.
```

That is a policy error, not a test failure, so nothing in the workflow runs and
the message is the only output. The `workflow-pins` check turns it into a local
lint finding instead.

Resolve a tag to its commit SHA — never copy one from memory or another repo:

```bash
gh api repos/actions/checkout/git/ref/tags/v4 --jq '.object.sha'
```

If `.object.type` is `tag` (an annotated tag) dereference it once more:

```bash
gh api repos/actions/checkout/git/tags/<sha> --jq '.object.sha'
```

Then pin with the human-readable release in a trailing comment, which is what
Dependabot reads when it proposes an update:

```yaml
- uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4.4.0
```

Beyond satisfying the policy, this is the correct supply-chain posture: a
mutable tag like `@v4` can be repointed at arbitrary code after review.

### Why `agent.yml` keys must not be nested

`agent.yml` looks like one mapping but is read as two. `agent:` carries the
identity — `id`, `language`, `persona`, `voice`. Everything else the engine
uses for prompt tuning is read from the **top level**, as a sibling of
`agent:`:

```yaml
agent:
  id: atlas-voice-travel
  persona: |
    You are Atlas…

rules:                      # <- top level, NOT indented under agent:
  - "Confirm irreversible changes before calling tools that change state."
```

Nest `rules:` inside `agent:` and nothing complains. `AgentSpec` is declared
`extra="ignore"`, and `_agent_spec_payload` only copies those keys off the root
mapping — so the block parses, is discarded, and the agent runs without the
guardrails you wrote. No warning at train time, no error at load.

This was not hypothetical. Every resource in this catalog had it: 39 rules
declared across 15 `agent.yml` files, including the paste-ready tutorial
scaffolds, and zero applied. It was found independently by
[Samrudha Kelkar](https://github.com/samrudh) and
[Daksh Varshneya](https://github.com/dakshvar22) while contributing, and
`agent-config-keys` exists so the next person does not have to find it again.

A companion unit test compares the check's key list against the installed
`rasa.calm_v2` source, so if a future release moves a key the test fails and
names the list to update — rather than the check silently enforcing an old
schema.

### The two skill authoring rules, in detail

These are the ones most likely to bite when writing a new skill, because both
fail *silently at runtime* rather than loudly at edit time.

**`session.*` is not substituted in prose.** It is evaluated in `if:`
conditions and structured fields (`requires:`, `when:`, `complete_when:`), but in
instruction text it is passed to the model as literal characters:

```markdown
<!-- wrong: the model sees the literal string -->
If `session.project.username` is empty, load the profile first.

<!-- right: substituted with the live value -->
If `@memory.project.username` is empty, load the profile first.
```

**`if:` only works at the top level of the skill body.** Indented inside an
`instructions:` scalar it is *not* parsed as a condition — it stays prose, and
the model is asked to interpret a condition it cannot evaluate:

```yaml
# wrong: this `if:` is inside an instructions block, so it is just text
  - id: collect_auto_fields
    instructions: |
      if: session.file_claim.policy_name == "Car"
      Ask for the incident time.

# right: express the branch in language, keep the guard structured
  - id: collect_auto_fields
    instructions: |
      When the selected policy type (@memory.file_claim.policy_name) is Car,
      ask for the incident time and set incident_time.
    complete_when: >
      (session.file_claim.policy_name == "Homeowner") or
      (session.file_claim.incident_time)
```

The linter models a `skill.md` as three stacked languages — YAML frontmatter,
markdown body, and `:::block` YAML regions — so `complete_when: >` continuation
lines and `parameters:` bindings are correctly treated as structured rather than
prose.

### Why wave projects are exempt from `version-consistency`

Not leniency, and deliberately narrow. Holding a past cohort's project to the
shared pin has two outcomes and both are worse than exempting it: either
`make migrate` rewrites the author's `Verified with:` line into a claim nobody
tested, or the build goes red for every past wave on every bump until someone
deletes their work. `snapshot-pin` is the replacement obligation — it asserts
the resource is *internally* honest and reproducible, which is the part that can
actually be verified.

`community/` is **not** exempt. It is maintained material: migrated with the
catalog, re-verified, and re-stamped by whoever does the bump. See
[`SNAPSHOTS.md`](SNAPSHOTS.md).

### Resources that need a provider key

A resource on a non-default provider declares the key it needs:

```toml
[tool.rasa-catalog]
required-secrets = ["GEMINI_API_KEY"]
```

`make ci` and CI then **skip** its `rasa train` with a warning when the key is
absent, instead of dying on an unexpanded `${GEMINI_API_KEY}` that reads as a
broken project. `make test-all REQUIRE_SECRETS=1` turns that skip back into a
failure. The trade is explicit: such a resource is CI-verified as far as install
and `validate_project` and no further, until the secret is added to the
repository — and its README is expected to say so.

## What `make ci` adds

For every project in the maintained catalog, `scripts/check_project.py`:

1. `uv sync` with the prerelease flag implied by the pin
2. asserts the installed `rasa-pro` equals `RASA_PRO_VERSION`
3. asserts `rasa.calm_v2` is importable — the guard that catches pinning a
   release without the Mantle engine
4. runs `validate_project`

`make ci` then runs `make check-snapshots`, which does the same four steps for
every frozen wave project with `--use-project-pin`: step 2 asserts the version
that resource pins, not the catalog's.

## What `make validate-full` adds

`rasa train` per project, which needs credentials. They resolve as:

1. exported shell variables
2. the project's `.env`
3. a `.env` at the repository root

The root `.env` is the maintainer convenience: one `RASA_LICENSE`,
`OPENAI_API_KEY`, and `DEEPGRAM_API_KEY` for all seven resources.

**A missing licence is a skip, not a pass.** By default `test-all` warns and
continues, which means a green run may have trained nothing. Pass
`REQUIRE_LICENSE=1` (as `validate-full` does) to make that a hard failure:

```bash
make test-all REQUIRE_LICENSE=1
```

## Continuous integration

[`.github/workflows/validate.yml`](../.github/workflows/validate.yml) runs on
push, pull request, and weekly.

- `validate` — the offline gate, with `STRICT=1`; uploads `lint-report.json`
- `upstream` — `make outdated`: the only job that queries PyPI
- `discover` — enumerates both tiers into matrices
- `check` — one runner per catalog project, `fail-fast: false`, so one broken
  resource does not mask the others; trains only where a `RASA_LICENSE` secret exists
- `snapshots` — one runner per frozen wave project, asserted against its own pin
  and never trained. A pull request checks only the snapshots it touched;
  scheduled and push runs check them all, which is where a yanked release or a
  rotted lock surfaces

The weekly run matters, and `upstream` is the job that earns it. Everything
else resolves against the committed `uv.lock`, so a new rasa-pro release is
invisible to them — the pinned version installs exactly as it did last week.
`upstream` reports the newest release *overall*, inspects it for the Mantle
engine module, and writes the verdict to the run summary, which is how a
release line stops being permanent by accident. It never fails the build: a new
upstream release is news, not a broken repository.

## Adding a check

Add a function to `scripts/lint_repo.py` returning `list[Finding]`, register it
in `CHECKS`, and add a regression test to `scripts/test_tooling.py`.

Write the test so it *fails against the bug*, not just passes against the fixed
tree — a check that cannot fail is worse than no check, because it reads as
coverage. For the same reason the runner asserts it collected tests at all: a
suite that silently runs zero tests exits 0 and reads as a pass, which has
happened here. The unit tests feed the extractor the exact broken skill text this
repository shipped, so each case is a regression that actually occurred rather
than a hypothetical.

## Related docs

- The frozen-snapshot contract: [`SNAPSHOTS.md`](SNAPSHOTS.md)
- Version bumps and release lines: [`MIGRATING.md`](MIGRATING.md)
- Resource metadata template: [`RESOURCE_TEMPLATE.md`](RESOURCE_TEMPLATE.md)
- Contribution rules: [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
