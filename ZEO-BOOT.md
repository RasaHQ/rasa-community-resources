# Booting rasa-community-resources under ZEO

## Claude Code

```bash
eval "$(./scripts/zeo-org seat use master)"
claude --agent zeo-master --permission-mode bypassPermissions

eval "$(./scripts/zeo-org seat use sparring)"
claude --agent zeo-sparring --permission-mode bypassPermissions

claude --agent zeo-stream --permission-mode bypassPermissions
```

Run each seat in its own shell. The `eval` must happen before Claude starts because
the child process inherits its GitHub identity from that shell. The Stream form
additionally requires a real stream id and packet.

## Codex

```bash
codex
```

Then explicitly request the persona, for example:

```text
Delegate to the subagent named zeo-master. It is the active Master for this
human-triggered session; have it orient through ./scripts/zeo-org before acting.
```

Codex has no Claude-style root `--agent` option. Its ZEO personas are the
project-scoped `.codex/agents/*.toml` subagents loaded by an explicit session.

Every seat first runs `./scripts/zeo-org orient --json`; it must report the
`org-rasahq` corpus and canonical Rev 17.
