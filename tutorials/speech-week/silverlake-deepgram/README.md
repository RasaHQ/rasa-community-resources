# Rasa + Jack Henry SilverLake + Deepgram: confirm a transfer by voice

Run a bank voice assistant that reads a fictional balance, reviews a transfer,
and waits for a separate confirmation. Deepgram handles recognition and speech;
OpenAI plans tool calls. The bank is a local SilverLake-shaped SOAP mock,
validated against Jack Henry's public jXchange definitions. Nothing contacts a
real bank. Saying “verify me” grants simulated teaching verification, not identity
proof. An accepted request is not a posted transaction.

This profile targets the **Rasa Pro 3.22.0rc1 release candidate**. It has its own
lock. The rest of the resources catalog keeps its existing Rasa version.
When the final release ships, this profile must be re-pinned and checked again.
No SDK patch is applied.

```text
Author:        Rasa Community contributors
Assessed on:   19 November 2026
Assessed by:   Native Inspector synthetic caller and local mock journal
Verified with: rasa-pro 3.22.0rc1, four recognized turns and one accepted mock operation
Installation:  rasa-pro 3.22.0rc1, Python 3.12
Audience:      Developers building banking voice assistants
Time:          Setup time has not been measured for this profile
Industry:      Banking
You learn:     Check recognized turns and durable mock effects before accepting a voice transfer test
Catalog name:  SilverLake Deepgram release-candidate voice profile
```

## Prerequisites and cost

Use GitHub Codespaces, Python 3.12 and uv. Save personal Codespaces secrets
`RASA_PRO_LICENSE`, `OPENAI_API_KEY` and `DEEPGRAM_API_KEY`, with repository access.
The license is available through [Rasa's key instructions](https://rasa.community/keys/).
Use accounts with authorized API usage. Codespaces, OpenAI and Deepgram can incur
charges. Do not use customer data. The setup checks which names are set. A successful provider request separately checks account access.
After changing secrets, stop and restart the Codespace. Never print their values.

## Start it

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-speech-week-silverlake-deepgram/devcontainer.json)

This release-candidate profile uses its own locked Rasa version; the rest of the catalog is unchanged.

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_PRO_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make run`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** the server starts on port 5005.
<!-- codespaces:end -->

Use the generated button above after this branch has passed review and merged.
For a source review before merge, use this branch's Codespace, not the main-branch
button. The source must include both this profile and `examples/jack-henry-silverlake`;
copying only this folder loses the bank host and tools it imports.

The managed experiment route, from the repository root, is:

```bash
python3 scripts/workspace.py start tutorials/speech-week/silverlake-deepgram --owner silverlake-deepgram-rc1
cd tutorials/speech-week/silverlake-deepgram
make download
make doctor
make test
```

The workspace command creates only this profile's locked environment. Preserve an
existing experiment before reusing its owner or environment. The download checks
the published archive hash before saving it in the bank example's vendor-inputs
folder. If it fails, stop; do not substitute an unverified archive. The native
configuration tests check the rc1 loader, required orchestrator, Deepgram channel and
source-only preparation. They do not call a speech or model service.

Then start the assistant:

```bash
DEMO_SEED=295185 make run
```

Wait for the printed server-ready line and Inspector link. Open that exact link
and enable the microphone if the browser asks. Keep the terminal running. A missing
key, archive or invalid configuration stops startup; read the safe error type,
correct the named prerequisite and retry startup, not a transfer.

## Speak, wait and check

Ask these questions separately, waiting for each answer before the next:

1. “What is the available balance of checking A?”
2. “Verify me.”
3. “Transfer twelve US dollars from checking A to savings A.”
4. After the review has finished: “Confirm transfer.”

For the recorded seed, the mock supplied USD 786.09 as the available balance.
Read your tool result rather than assuming the same words or value on another
seed. The simulated verification lasts about a minute; if it expires, obtain a
new verification and request a fresh review. Do not combine the transfer request
and confirmation into one sentence. The host requires confirmation on a separate
next turn. Any different reply cancels the review.

The recorded run's final notice was: “The transfer request was accepted. Accepted
does not mean posted.” Check the tool result and journal as well as the words.
Stop with Ctrl+C. Preserve the journal if an outcome is uncertain; never send a
second transfer merely to discover whether the first succeeded.

## Recorded scope and the caller-feed correction

On November 19, one headless native Inspector run used Deepgram Nova 3 input,
Deepgram Aura 2 output and a synthetic caller. Four recognized user turns led to
simulated verification, a review and one accepted local-mock operation. Audio was
captured; playback acknowledgements were simulated, with no human listening
assessment. The retained observation covers this synthetic conversation and its mock journal.
Human listening quality, latency and production banking readiness require their
own evaluations.

The earlier caller client sent a short silence followed by a wire gap. Recognition
combined its four clips into two turns and no operation was accepted. The corrected
client reused the same four WAVs and streamed PCM silence between utterances.
The corrected feed produced four recognized turns in this observation. Vendor
fault attribution would require separate evidence. The existing
`scripts/case_builds/voice_driver.py` also uses continuous silence, on the older
browser_audio transport. Its historical success is not an rc1 Inspector result.

`record_voice_once.py` records a new paid synthetic session when explicitly run.
It has an exclusive one-attempt intent per private absolute state directory,
records events/audio locally and shuts down the server it starts. It generates
four caller clips through Deepgram unless `--caller-clips` names existing WAVs.
Keep these outputs private; tracker and server logs can contain runtime details.
The process exit code means observations were recorded, not that acceptance passed.
Inspect recognized turns, tool results and the SQLite journal before making a claim.

`make text` is a separate REST-only developer check. Typed messages check the model and tool route. Qualify the speech path with a
separate recorded voice session. The existing bank README documents the mock, schema archive and
journal behavior; its older runtime assessment does not qualify this rc1 profile.

`make run` and `make text` fetch and verify the required public bank archive first. The recorder refuses a foreign listener on port 5005, then uses a fresh per-attempt port consistently for its child, readiness probe and client. Before sending a session request or audio, the Linux Codespaces recorder checks that the connected WebSocket peer belongs to its child process group using kernel socket records. It refuses missing or foreign ownership and never terminates the foreign listener. This automated recorder requires Linux `/proc`; use the Inspector manually on other systems.

`make doctor` checks only key presence, the installed version and local vendor definitions; it prints no secret values and makes no provider request. A profile-local `.env` is loaded without replacing exported Codespaces secrets, before the license-name alias is applied. That file is never copied into the temporary Rasa source project.
