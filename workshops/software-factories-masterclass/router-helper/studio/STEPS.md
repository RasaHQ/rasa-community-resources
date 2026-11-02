# Studio path: the router restart helper

These steps use the Studio 1.15.2 interface. Build the helper in Studio, then test
both the conversation and the command it records.

1. Sign in and create an assistant project.
2. Open **CMS → Slots**. Create `confirm_restart` (Boolean), `command_sent` (Text),
   and `reset_kind` (Text).
3. Create a flow with ID `restart_router` and name **Restart router**. Use this
   description:

   > Start this flow ONLY when the customer explicitly asks to restart or reboot
   > their router. Do not start this flow for any request containing the word
   > reset, including reset it or reset my router; those requests belong
   > exclusively to reset_router and need clarification.

4. At the bottom of **Start**, add **Collect information**. Select
   `confirm_restart`. Under **Select or create response**, choose **Create new
   response**, name it `utter_ask_confirm_restart`, and enter:

   > I can restart your router now. Your internet will drop for a short time, and
   > your Wi-Fi name and password stay the same. Shall I go ahead?

   Save the response, select it in the response list, then choose **Select
   response**. Describe the information being collected as confirmation of a
   restart. Use the bottom **+** on a node to append the next step; a **+** on an
   existing connection inserts a step before the following node.
5. Append **Logic**. Select its first condition branch, then choose
   `confirm_restart` → **Is** → **True**.
   - On that branch, append **Set slots**: `command_sent` → **Is set to** →
     `REBOOT`. Append **Send message** and create/select `utter_restart_sent`:
     *Done. I sent a restart (REBOOT). Your Wi-Fi name and password are kept.*
   - On **Else**, append **Send message** and create/select
     `utter_restart_declined`: *No problem. I have not sent anything to your
     router.*
6. Create a second flow with ID `reset_router` and name **Clarify router reset**.
   Use this description:

   > Handle all requests to reset, including reset it, reset my router, and
   > factory reset. If the customer says reset it, start this flow to clarify
   > whether they mean a restart or factory reset. A reset request must not start
   > restart_router directly.

   Add **Collect information** for `reset_kind` and create/select the response
   `utter_ask_reset_kind`: *Do you mean a restart, or a factory reset?* Describe
   the collected information as `restart` or `factory reset`. Append **Logic**:
   `reset_kind` → **Is** → `restart`. On that branch add **Link**, select
   `restart_router`. On **Else**, create/select a **Send message** response:
   *I cannot do a factory reset here. I can connect you with a person.*
7. Open **Train**, include both flows, and select **Draft** for each flow when
   testing your current edits. **Published** uses the earlier published
   snapshot; a description visible in the editor is not proof that snapshot
   contains it. Choose **Start training** and wait for **Training successful**.
   Open **Try your assistant** and run the four checks from the run sheet.
   Use **Restart conversation** between separate cases.
8. To run the first file check, download the project to files and point the check
   at its flows file: `rasa studio download` (see Rasa's Studio tutorial for the
   one-time `rasa studio config` and `rasa studio login`), then
   `python3 ../check_helper.py data/studio_flows.yml`.

Studio licence: the repository's Studio setup uses `RASA_STUDIO_LICENSE`. The free
Developer Edition key did not unlock Studio in testing.
