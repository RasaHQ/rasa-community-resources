# Tutorial recovery checkpoints

Optional git tags you can create before a live session so presenters can jump
forward or recover. The finished agent on `main` is always the primary escape
hatch (`make inspect`).

Suggested tags:

| Tag | Meaning | Recover with |
| --- | --- | --- |
| `tutorial/step-00` | Scaffold + voice shell | `git checkout tutorial/step-00 -- agent.yml integrations.yml memory.yml responses.yml skills/intro` |
| `tutorial/step-01` | FAQ skill | `git checkout tutorial/step-01 -- skills/trip_faq` |
| `tutorial/step-02` | First tool + DB | `git checkout tutorial/step-02 -- skills/check_itinerary tools lib data/source` |
| `tutorial/step-03` | Flight status constraints | `git checkout tutorial/step-03 -- skills/flight_status` |
| `tutorial/step-04` | Scoped instructions | `git checkout tutorial/step-04 -- skills/flight_status` |
| `tutorial/step-05` | Baggage ordered block | `git checkout tutorial/step-05 -- skills/report_baggage` |
| `tutorial/step-06` | Composition | `git checkout tutorial/step-06 -- skills/authenticate skills/find_booking skills/change_booking` |
| `tutorial/step-07` | Remaining skills | `git checkout tutorial/step-07 -- skills tools lib` |

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
