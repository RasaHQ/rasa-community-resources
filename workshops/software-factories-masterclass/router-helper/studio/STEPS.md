# Studio path: the router restart helper

Build the helper in Rasa Studio. The labels below follow Rasa's Studio tutorial and docs and
have not yet been checked click by click in a workshop run.

1. Sign in with your Studio account and create an assistant project.
2. Open **Slots** and create two slots: `confirm_restart` (Boolean) and `command_sent` (Text).
3. Create a flow named `restart router`. Give it the description: *The customer wants to restart
   their router.* Leave the start step on the default, so Rasa starts the flow from the description.
4. Add a **Collect information** step for `confirm_restart`. Add a response for the question:
   *I can restart your router now. Your internet will drop for a short time, and your Wi-Fi name
   and password stay the same. Shall I go ahead?* Give the step a description that says what is
   being confirmed.
5. Add a **Logic** step on `confirm_restart`.
   - If it is true: add a **Set slots** step that sets `command_sent` to `REBOOT`, then a **Message**
     step: *Done. I sent a restart (REBOOT). Your Wi-Fi name and password are kept.*
   - Otherwise: add a **Message** step: *No problem. I have not sent anything to your router.*
6. Create a second flow named `reset router` with the description: *The customer says only "reset"
   about their router.* Add a **Collect information** step for a Text slot `reset_kind` that asks
   *Do you mean a restart, or a factory reset?* If the answer is a restart, **Link** to the
   `restart router` flow. Otherwise add a **Message**: *I cannot do a factory reset here. I can
   connect you with a person.*
7. **Train**, then use **Try your assistant** to run the four checks from the run sheet.
8. To run the first check, download the project to files and point the check at the flows file:
   `rasa studio download` (see Rasa's Studio tutorial for the one-time `rasa studio config` and
   `rasa studio login`), then `python3 ../check_helper.py data/studio_flows.yml`.

Studio licence: you need a Studio licence (the codespace secret `RASA_STUDIO_LICENSE`) for the Studio
setup in this repository. The free Developer Edition key did not unlock Studio in testing.
