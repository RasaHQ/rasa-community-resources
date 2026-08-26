# Recovery tags

After the finished tutorial lands on your branch, create annotated tags that
match the live chapters so an unrehearsed presenter can recover mid-session:

```bash
git tag -a tutorial/step-00 -m "Scaffold: agent.yml + Deepgram integrations"
git tag -a tutorial/step-01 -m "FAQ prose skill"
git tag -a tutorial/step-02 -m "check_balance tool (no constraints)"
git tag -a tutorial/step-03 -m "check_balance tool_constraints"
git tag -a tutorial/step-04 -m "block_card progressive control"
git tag -a tutorial/step-05 -m "transfer_money composition"
git tag -a tutorial/step-06 -m "Full skill parity"
git tag -a tutorial/step-07 -m "Voice Deepgram demo-ready"
```

Restore one checkpoint without rewriting history:

```bash
git checkout tutorial/step-04 -- skills tools lib agent.yml integrations.yml
make train
```

Paste-ready files for each chapter also live under `tutorial/snippets/` and do
not require tags.
