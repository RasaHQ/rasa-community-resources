# Reproduce the fictional clinic calls locally

`conversations.json` defines fictional caller inputs and expected clinic tool
behavior. The shared runner starts the selected implementation, streams the
synthetic caller audio and writes local output. `checks.py` checks identity,
medicine selection and caller confirmation from the clinic audit. Offline
tests use scripted model answers and fake speech services.

```sh
# From the tutorial root; paid provider calls require local credentials.
python3 shared/spec/run_spec.py rasa --label my-run --results-root /path/to/private/output --budget-usd 4
# Select another implementation by replacing rasa with its directory name.
make test
```

The Rasa runner trains the selected project before starting it. The other
implementations start their own server. Use `--mode text` to skip speech
recognition, `--only <conversation-id>` to select a caller input, and
`--spec <file>` for an alternate fictional input file. See `--help` for server
commands, readiness limits and speech-price configuration. Provider calls
incur charges; the budget cap includes model usage and priced speech.

Keep output labels unique so every local attempt is retained. Output includes
caller turns, tool effects, usage, summaries and logs. These generated records
are private local artifacts and must not be committed to the public tutorial
repository. `--results-root` places them outside the source checkout.

Caller WAVs are synthetic speech for invented patients. Their manifest binds
text and audio hashes for reproducibility. Regenerate changed inputs with the
caller-audio tool and check them before a run. Keep dependency locks, local
output and unique recordings when retiring an inactive Python environment.
