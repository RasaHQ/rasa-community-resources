# Addendum to the participant pre-work: message for the organizer to send (DRAFT, not sent)

FINAL TEXT only after the placeholders below are filled and the 17:00Z clean-clone measurement is in. This pack does not message participants. The organizer decides whether, when and how to send it, and to whom. It does NOT replace the earlier pre-work (sha256 c894ff24ad1572565fcf897df7e74379aae3879ef27528ec80e83532e180a568); it adds to it.

Placeholders: <CLASS_COMMIT> = the one RasaHQ/rasa-community-resources commit with PR 120 and PR 121 merged; <DOCTOR> = rasa's doctor command; <SCRIPTED> = rasa's one-command scripted replay; <MB> and <MINUTES> = measured on a clean clone: on one arm64 Mac, cold uv cache, fast connection (2026-10-21, PR121 head 1181c19, dev17 wheel staged): worker environment 1 second and 41 MB; project environment 20 seconds and 750 MB (cache 766 MB). So about 800 MB extra. A slower connection scales it; I say 'up to 10 minutes'. Not measured on Windows, Linux or a second machine.

---

Subject: Before Thursday 22 October: one more setup step, up to 10 minutes, once

If you already did the earlier 15-minute setup, do this too. If you did not, do the earlier steps first. Do it once, with a normal internet connection. It downloads about 800 MB in addition. In the room we will not do it.

1. Move to the class version of the repository. In the folder where you cloned it: `git fetch origin` and then `git checkout <CLASS_COMMIT>`.
2. Build the two environments for the product. From the repository root, one command at a time:
   `python3 scripts/workspace.py start examples/mantle-flight-briefing-openai-agents/worker --owner class-worker`
   `python3 scripts/workspace.py start examples/mantle-flight-briefing-openai-agents/project --owner class-project`
   `uv` will fetch Python 3.12 for these if you do not have it.
3. Run the check: <DOCTOR>
   Before the class it should say that both keys are MISSING and that the SCRIPTED path will run. That is correct. You do not need a key before the class.
4. Run the offline replay: <SCRIPTED>
   You should see cards marked REPLAY and the word SCRIPTED on screen.
5. If step 3 or 4 does not do that, bring the laptop anyway and tell us what it printed.

About the keys: we hand out the API keys in the class. You bring none. When we give you one, paste it only into your own terminal, in the way we show you. Never put a key in a file, an email, a chat or a screenshot.

---

Notes for the organizer:
- The earlier pre-work pins e2a286a8; this addendum moves participants to <CLASS_COMMIT>. The factory lock does not change, so the earlier environment stays valid (check: `git diff e2a286a8e496aeee0ad2a695031165361693ea8a <CLASS_COMMIT> -- workshops/software-factories-masterclass/factory/uv.lock` prints nothing).
- Not tested on a second machine or on Windows or Linux unless stated here after measurement.
