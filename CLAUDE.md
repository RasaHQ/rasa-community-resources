# rasa-community-resources ZEO entrypoint

This is an implementation repository. Its organizational records live in
`rodriveracom/org-rasahq`, not in this repository.

@../../rodriveracom/org-rasahq/governance/GOVERNANCE.md
@../../rodriveracom/org-rasahq/SEATING.md

## First act

Run `./scripts/zeo-org orient --json`, then read
`../../rodriveracom/org-rasahq/projects/rasa-community-resources/CLAUDE.md` and
the current SOW selected by the orientation result.

Never run `zeo init` here. Use `./scripts/zeo-org` for every ZEO command from
this repository.

The offline gate is `make validate`; `make ci` adds real installs and
`make validate-full` adds credentialed training.
