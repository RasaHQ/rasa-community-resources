# Codex entrypoint for rasa-community-resources

First run:

```bash
./scripts/zeo-org orient --json
```

This is an implementation repository associated with
`../../rodriveracom/org-rasahq`. Use `./scripts/zeo-org` instead of bare `zeo`.

Project-scoped Codex personas are installed at `.codex/agents/`:

- `zeo-master`
- `zeo-sparring`
- `zeo-stream`

They are constructors for explicitly requested subagents, not proof of occupancy.
The offline gate is `make validate`; `make ci` and `make validate-full` are deeper
credential/dependency tiers.

See `ZEO-BOOT.md` for the tested Claude Code and Codex invocation shapes.
