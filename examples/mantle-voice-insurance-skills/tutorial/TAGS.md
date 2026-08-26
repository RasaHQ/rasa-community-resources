# Tutorial recovery checkpoints

Optional git tags you can create before a live session so presenters can jump
forward or recover without a dry-run. The finished agent on `main` is always the
primary escape hatch (`make inspect`).

Suggested tags (create locally if useful):

| Tag | Meaning | Recover with |
|---|---|---|
| `tutorial/step-00` | Scaffold + voice shell only | `git checkout tutorial/step-00 -- agent.yml integrations.yml memory.yml responses.yml skills/intro` |
| `tutorial/step-01` | FAQ skill present | `git checkout tutorial/step-01 -- skills/insurance_faq` |
| `tutorial/step-02` | First tool + DB helpers | `git checkout tutorial/step-02 -- skills/view_policies tools lib data/source` |
| `tutorial/step-03` | Claim status + constraints | `git checkout tutorial/step-03 -- skills/check_claim_status` |
| `tutorial/step-04` | File claim showcase | `git checkout tutorial/step-04 -- skills/file_claim` |
| `tutorial/step-05` | Composition with inspection | `git checkout tutorial/step-05 -- skills/check_claim_status skills/schedule_inspection` |
| `tutorial/step-06` | Full remaining skills | `git checkout tutorial/step-06 -- skills tools lib` |

After any checkout:

```bash
make verify
make train
make inspect
```

If tags were never created, paste from [`snippets/`](snippets/) or reset:

```bash
git checkout main -- skills tools lib agent.yml integrations.yml memory.yml responses.yml
make train
```
