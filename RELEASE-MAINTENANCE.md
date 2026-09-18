# Rasa release maintenance

The trusted workflow checks PyPI every six hours at 03:23, 09:23, 15:23 and
21:23 UTC. It selects the latest non-yanked Python 3.12 wheel, including
prereleases, verifies its hash and requires the Mantle engine. It migrates the
maintained project pins, locks and installation references, preserving
historical assessed-on records, then runs the catalog gates and licensed
training for every maintained project.

Passing routine updates open a tested PR and attempt a normal merge of its
exact head. GitHub's required checks and reviews still apply. No administrator
bypass is used. Set repository variable `RASA_RELEASE_AUTO_MERGE=false` to
retain the PR for manual merge. An automated merge explicitly dispatches
`validate.yml` because token-originated pushes may not start another workflow.
The website follows on its own six-hour schedule; Netlify approval stays manual.

Failures stop publication and retain a 90-day `rasa-release-maintenance`
artifact. Start with `HANDOFF.md`: it gives the failing command, source commit,
recommended repair and reproduction steps. `run.json` records command outcomes;
`discovery.json` records the release even when migration fails. The packet also
contains the candidate patch, compatibility receipts and redacted project logs.
`proposal.json` distinguishes an unmerged PR from a successful merge followed
by a failed validation dispatch. No issues or messages are sent automatically.

Local reproduction requires Python 3.12, uv, the Rasa licence and the provider
credentials declared by the maintained projects:

```sh
uv run --with packaging==26.3 python scripts/releases/maintenance.py --kind catalog
```

Local runs never push or merge. Read the patch before applying it. Repair API
changes in the runnable example and matching tutorial together, then rerun all
gates. Website article changes require fresh audience assessments. Neither a
failed test nor missing credentials should be converted into a passing check.
