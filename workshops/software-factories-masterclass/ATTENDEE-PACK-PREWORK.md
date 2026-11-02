# Attendee pack, variant B: prepare the day before

Use this variant if opening a codespace and building the first agent takes too long to do inside the session. In one cold test the Mantle path took about 10.5 minutes from opening to a working reply, but starting Studio took about 9 more minutes, 16 minutes from opening in all. So anyone who will use Studio in the session should do at least step 4 below the day before. Variant A is `ATTENDEE-PACK.md`, where you do everything in the session. The organizers pick one variant for the room.

Never paste a key into a command, a file, or a chat.

## The day before (about 25 minutes, mostly waiting)

1. Do steps 1 to 5 of "Before the session" in `ATTENDEE-PACK.md`: your GitHub account, your Developer Edition key, your OpenAI key, the Studio licence from Rasa, and the three Codespaces secrets with **Repository access** set to the exact repository you will open.
2. Create your codespace from that repository with at least 4 cores, and open its terminal. Wait for the line that starts `Setup finished`.
3. Do the Mantle path in `ATTENDEE-PACK.md` as far as `rasa train`. Do not wait for the Inspector.
4. Start Studio once: `bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/start-studio.sh`. Wait for it to print the two addresses. This downloads the Studio files and images now, so they are not downloaded in the session.
5. Stop the codespace from the GitHub Codespaces page. It keeps your files. A stopped codespace costs only storage.

## The morning of the session (two minutes)

1. Start the same codespace and open its terminal.
2. Run: `bash /workspaces/rasa-community-resources/.devcontainer/software-factories-workshop/morning-check.sh`
3. Every line should say `OK`. For a line that says `NOT READY`, do the one fix it names, then run the check again. If you cannot fix it in two minutes, tell the presenter before the session.

## In the session

You are already past "open your codespace". Go straight to "Minutes 10 to 30" in `ATTENDEE-PACK.md`. The Inspector start (`rasa inspect --port 5010`) and the Studio start (`start-studio.sh`) take a few minutes the first time in a morning, so start them when the presenter finishes the opening.
