# Current Rasa compatibility

The daily `rasa-release.yml` workflow selects the highest non-yanked PEP 440 wheel version compatible with Python 3.12, including prereleases. It downloads the wheel, verifies the PyPI SHA-256 and requires `rasa/mantle/`. It reports the newest stable release separately. It does not silently select an older version if the candidate lacks the engine.

The authoritative selection implementation is `scripts/releases/index.py`, with regression tests covering final, prerelease, postrelease, new major, yanked and Python-incompatible versions. The older `make latest` interface retains explicit release-line controls for historical migrations; daily maintenance uses `scripts/releases/update.py` and does not use that fence.

`python scripts/compatibility.py --train` installs every maintained project from its committed lock, checks the installed Rasa version, validates the project, and requires licensed training. It discovers and runs project unit tests. The casebook adds all 62 scenario oracles, 186 mutation kills and 62 calls through the SDK adapter's injected-context convention. The CRM tutorial exercises its local mock MCP servers. The starter-pack check extracts its actual YAML examples, validates them with the SDK and rejects model-writable project memory through the linter.

`COMPATIBILITY.json` records the version, time, source hashes and passed scope. Its report is written only after every command succeeds. Unit tests and synthetic backend fixtures are not a claim of tested production integrations. Voice calls and every possible model conversation remain outside this receipt. The website separately runs four licensed quickstart text conversations.

Existing `Assessed on` and `Verified with` lines are historical human records. `Installation` is the moving pin. An automated migration must not rewrite a historical assessment into a new human verification claim.

## Daily operation

- The workflow runs at 03:23 UTC on the default branch and can be dispatched manually. GitHub schedules may be delayed.
- Required repository secrets: `RASA_LICENSE`, `OPENAI_API_KEY`, plus provider keys declared for training by catalog projects. Gemini uses local embeddings during training and declares an empty `training-secrets` list; its runtime still requires `GEMINI_API_KEY`. Missing required credentials fail training; they do not count as success.
- Every daily run tests the adopted release. A new version updates manifests before resolving locks, then tests the complete catalog. Only a passing candidate is proposed on `automation/rasa-VERSION`.
- Failure leaves main unchanged and uploads redacted logs and a candidate patch for investigation. No issues are opened by this repository's automation.
- A PR is reviewed and merged by the operator. The website then pins that exact companion commit and performs its own complete build, source inventory, download and live conversation gates.
- Pull-request checks run without credentials. Trusted scheduled checks run on main; there is no `pull_request_target` execution of candidate source.

The workflow runs its gates before creating the PR, so token-created PR trigger restrictions cannot create an untested update. Once merged, ordinary main checks run too. Workflow schedules become active only after their files reach main.

References: [PyPI version history](https://pypi.org/project/rasa-pro/#history), [Rasa changelog](https://rasa.com/docs/reference/changelogs/rasa-pro-changelog/), [GitHub scheduled events](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule), [GitHub workflow triggering](https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/trigger-a-workflow).
