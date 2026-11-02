# Presenter notes

Sixteen slides for the New York edition, Tuesday 3 November, 3:00 to 6:00 PM New York time. Minute 0 is 3:00 PM. The timing source is `../RUN-SHEET-DARK-FACTORY.md`. Press N in the deck to show these notes on screen.

Every attendee works in a GitHub Codespace on Rasa Mantle only. Nothing is set up in advance. Say what was measured and what was not: testers have run the first 30 minutes in fresh codespaces with help, and nobody has yet done it unaided.

## 1. A dark software factory built in your own codespace.

Welcome briefly. Say where the work happens: everyone builds in a GitHub Codespace in the browser, so nothing is installed on a laptop. The helper simulates a router command. It contacts no router and changes nobody's internet connection. Do not demo anything before slide 4.

## 2. Three hours, mostly your hands on the keys.

Use elapsed minutes and the clock: minute 0 is 3:00 PM, minute 30 is 3:30, the break is minutes 70 to 75 (4:10 to 4:15), the builder starts at minute 75, the gate at 115 (4:55), release at 140 (5:20), the Studio 2 preview at 160 (5:40) and the close at 175 (5:55). If time is short, shorten the release block first and keep the first 30 minutes whole. The preview is short; the rest of its block is slack.

## 3. Open your codespace now, at minute 0.

Keep this slide up while people open codespaces and show the finished helper from the next slide on a second screen if you can. Exact steps are in ATTENDEE-PACK.md. The install can run for several minutes after the codespace shows as available: wait for the line that starts Setup finished. NOT READY names the secret to fix; fix it, then stop and start the codespace. Never let anyone paste a key into a chat, a command or a file. Pair anyone who cannot open a codespace with a neighbor and do not troubleshoot billing in the room. Setup time for a first-time attendee has not been measured.

## 4. One small agent: a router restart helper.

This is the one risk the whole session protects: a restart and a factory reset sound alike, and a factory reset would erase the customer's Wi-Fi name and password. Show the finished helper once, typing the four rows. The wording differs a little between runs; the meaning must match. Say plainly that the command is simulated.

## 5. Minutes 10 to 30: build your helper.

The slide shows the shape of the steps; the attendee pack has the exact commands with full paths, so tell people to copy from the pack, not from the slide. The installer moves the starter banking skills out of the active skills and sets a router-only persona. After rasa inspect says the server is up and running, a second terminal runs print-inspector-url.sh to print the Inspector address; if GitHub asks to continue to a private port, choose Continue. In test codespaces the helper first confirmed a restart about 10 minutes after the codespace opened. Testers had help and used an existing account. Nobody has done this unaided yet, so say so if people run slow.

## 6. Target at minute 30: all four rows.

Walk the room and ask each person to read one reply aloud. If someone is stuck at minute 25, pair them with a neighbor and keep going. The measured times are for the presenter, not the slide: in test codespaces the first confirmation came about 10 minutes after opening and all four rows by about 11 minutes, with help and an existing account. A row that does not match: write down the words on screen, not keys, and ask early. Do not retry an unchanged key that was rejected. The measured numbers come from automated-assisted test runs; do not present them as a promise.

## 7. Minutes 30 to 50: try to break your helper.

Ask three questions on paper: who wrote the confirmation, you or the engine? Where is REBOOT stored? What files does the helper keep? The target at minute 50 is a helper that never records anything the customer did not ask for. After a first message or a restart the engine can still add its normal follow-up question, so the refusal may not be the only text. Treat that as normal, not as a failure.

## 8. A check that reads the file, not the reply.

Run it, see PASS, change REBOOT to FACTORY_RESET in tools.py, run it again, see FAIL, then change it back to REBOOT and run it again to see PASS before anyone moves on. The builder part later retrains the helper, so a wrong command left in tools.py would be carried into it. The point: the helper's reply can still sound right while the file is wrong, and a check on the file catches it. Be clear about the limit: it exits 2 when it finds no command, so a missing command is never a pass, but it is a source-file check, not a run-time trace.

## 9. Break.

Anyone who needs to leave now leaves with a working helper (four conversation checks passing) and a source-file check that catches a wrong command and passes again once REBOOT is restored. Check those two things separately. Use the break to help anyone who is behind catch up on the four rows.

## 10. The factory begins: your builder.

In a new terminal, run builder.py from the pack's builder block. Keep the printed path for the gate. The builder is told to write and save a file but not to run it. Model use is billed at the model's rates; the cost of one run was not measured, so do not quote a number. If a session fails (permissions, quota, model), the presenter runs one builder on the screen and everyone takes router-helper/gate/candidates/good.py to the gate.

## 11. Put the builder behind your helper.

Three terminals, each with its own B variable; the pack's builder block has all three exact commands. The installer copies the change_builder skill into the agent and raises Mantle's tool wait from 10 seconds to at least 450, because a build takes minutes. Stop the Inspector with Ctrl+C in its own terminal, never terminal 2. This part ran once on the latest code with a real key: 28 seconds from message to reply in a test codespace. It has not been followed by an attendee, so say so if it fails.

## 12. A request goes in. A proposed change comes out.

Target at minute 115: a request goes in and a proposed change comes out. Nothing is applied: the file sits in the builder's own folder. If the tool server or its wiring will not work, call the builder from its script and carry the saved file forward. Never ask a second time before reading terminal 2.

## 13. A gate the builder cannot edit.

Run gate.py on the saved path, then on the four candidate files, and compare. The gate prints ACCEPT or REJECT and the names of the tests that failed. It reads the file once and judges those bytes, so a change cannot write a file or open the network while it is judged. This fits one small read-only operation and is not a general sandbox. If the gate says it could not judge, show a recorded ACCEPT and REJECT, labeled as recorded. On Linux this ran in a test codespace and returned ACCEPT for a freshly built file.

## 14. You are the last gate.

Run the whole line once, end to end, and record the decision. The exercise outcome is a recorded approval or refusal for manual review: nothing is installed or applied to the helper, and a gate ACCEPT is not a deployment. The principle: the check belongs to someone other than the builder, and a person stands at a few defined gates. Passing is bounded evidence, not proof of all future behavior. If the line is not working for someone, they follow the presenter's recorded run and note which parts they could not complete.

## 15. A Studio 2 preview.

Say it is an early preview that attendees cannot try yet, then show it live from your own machine for a few minutes. Keep your own setup notes outside this repository; do not say how to get the preview, and keep keys, licences and any command line off the shared screen. Have a recording ready in case the live start fails. End with the call to action: join the Rasa Community at info.rasa.com/community to hear when Studio is released.

## 16. Describe, build, check, release.

Show the line once more with the pieces each person built: the helper, the source-file check, the builder, the gate and their own decision. Name the one check each person could not edit. Close on the question and the community link from the previous slide.
