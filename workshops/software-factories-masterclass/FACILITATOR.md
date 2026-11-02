# Facilitator notes: dark software factory workshop

For the person presenting. The timing source is `RUN-SHEET-DARK-FACTORY.md`. The slides are in `slides/` and the note for each slide is in `slides/PRESENTER-NOTES.md`. Attendees follow `ATTENDEE-PACK.md`.

Everything runs in GitHub Codespaces on Rasa Mantle. Nothing is installed on a laptop and nothing is set up in advance.

## Before the room opens (about 20 minutes before 3:00 PM)

1. Open the workshop codespace yourself, on the room's network, from the link the workshop lead sends. Use the `software-factories-workshop` configuration with at least 4 cores. Wait for the line that starts `Setup finished`. Note how long it took.
2. Run the four checks of the router helper once, so you have seen the real replies (ATTENDEE-PACK.md, minutes 10 to 30).
3. Open the deck (`slides/index.html`) offline and check the notes with the N key.
4. Put the "If something fails" table of the attendee pack on a second screen.
5. Prepare your Studio 2 preview on your own machine and a recording of it. Keep its setup out of this repository and off the shared screen.

## Running the room

- Each person works alone at their own codespace. Pair anyone who cannot open one with a neighbor, and do not troubleshoot billing in the room.
- Minute 0: everyone opens a codespace while you show the finished helper. The install can run for several minutes after the codespace shows as available.
- Use a two-minute intervention. Ask for the last step that worked, read the exact words on screen (never a key), offer the documented recovery, then let them continue. A `NOT READY` line names the secret to fix, and a codespace that was already running needs a stop and start after a secret is added.
- At minute 30 move on even if some rows do not match. At minute 70 take the break. At minute 115 anyone without a saved builder file takes `router-helper/gate/candidates/good.py` to the gate.
- If time is short, shorten the Studio 2 preview first, then the release block. Never shorten the first 30 minutes.

## Say what was measured, and what was not

- In test codespaces the helper first confirmed a restart about 10 minutes after the codespace opened and all four checks passed by about 11 minutes. Testers had help and used an existing account.
- The builder and the tool server ran once on the latest code with a real key: 28 seconds from message to reply in a test codespace.
- Not shown: an unaided first-time attendee, a fresh account on the room's network, the cost of a builder run, and a real router.

## Never equate

- A builder session that finished with an accepted change.
- A source-file check passing with the helper running that command in a conversation.
- A passing gate with proof of all future behavior.
- The Studio 2 preview with something attendees can use.

## Closing prompt

Ask each person to name the one check they could not edit, and the one decision they made at the last gate.
