# Recovery checkpoints

Use these as mental (or local git) tags during a live session. The finished
agent on the current branch is always the safety net.

| Tag | Meaning | Recover by |
|---|---|---|
| `tutorial/step-00` | Scaffold + voice configs present | Paste `tutorial/snippets/step-00-scaffold/` |
| `tutorial/step-01` | FAQ skill works | Paste `tutorial/snippets/step-01-faq/` → `skills/telco_faq/` |
| `tutorial/step-02` | Check-bill tool works | Paste `tutorial/snippets/step-02-check-bill/` |
| `tutorial/step-03` | Bill-month constraint enforced | Paste `tutorial/snippets/step-03-tool-constraints/` |
| `tutorial/step-04` | Reset-router showcase complete | Paste `tutorial/snippets/step-04-reset-router/` |
| `tutorial/step-05` | Internet composition wired | Paste `tutorial/snippets/step-05-internet/` |
| `tutorial/step-06` | Remaining skills present | Paste `tutorial/snippets/step-06-remaining/` |
| `tutorial/finished` | Full agent | Stay on finished tree; `make verify && make train && make inspect` |

## Quick recovery commands

```bash
make verify
make train
make inspect
make show-demo-data
make reset-db
```

If paste sets drift from the finished tree, prefer the finished `skills/`,
`tools/`, and `lib/` directories — snippets are teaching copies, not a second source
of truth.
