# Build and check a router helper in GitHub Codespaces

**New York workshop — Tuesday, November 3, 2026, 3:00–6:00 PM Eastern.**
A hands-on session by Rod Rivera for developers who want to connect an agent to
tools, inspect a proposed code change, and decide whether to accept it.

You build a small Rasa Mantle helper that asks before recording a simulated
router restart. Then you connect a builder, inspect its saved proposal, and
accept or reject it with a separate check. The exercise contacts no router.
Its final result is a recorded review decision, with nothing installed or
applied automatically. Attendees use Mantle throughout.

## Start here at minute 0

Nothing needs to be set up before the workshop. You need a browser, your own
GitHub account, your own free [Rasa Developer Edition key](https://rasa.com/rasa-pro-developer-edition-license-key-request),
and your own [OpenAI API key](https://platform.openai.com/api-keys). Request or
retrieve the keys at minute 0 if needed. The Rasa form's confirmation page is
not the key. Model usage is billed to your OpenAI account; the practice builder
starts no Agents session.

1. In GitHub, open **Settings → Codespaces**. Add `RASA_LICENSE` and
   `OPENAI_API_KEY` as account secrets. Under **Repository access**, include
   **RasaHQ/rasa-community-resources**, the repository opened by the link below.
   If either secret already exists, edit its access instead of creating a
   duplicate, and retain any other repository access you still use. Never put a
   key in source, a command, a shared log, or chat.
2. **[Open the workshop Codespace](https://codespaces.new/RasaHQ/rasa-community-resources?devcontainer_path=.devcontainer/software-factories-workshop/devcontainer.json).**
   Select the **New York workshop: Rasa Mantle** configuration and at least
   **4 cores**. Create the Codespace. Python, uv, and the two locked environments
   are prepared automatically; you do not install them on your laptop.
3. Wait for dependency preparation, then the terminal line beginning
   **`Setup finished`**. An available editor alone does not mean setup finished.
   The setup check verifies license handling and the presence of the model key;
   the helper conversation checks model access.
4. Open the [attendee pack](ATTENDEE-PACK.md), starting with **Your router
   helper**. Copy its full commands in order. Keep the terminal running where a
   server is running; the pack names when to open another one.

**Reviewing an unmerged change:** use the repository and branch named in the
review handoff. Open that branch on GitHub, choose **Code → Codespaces → New
with options**, and select the same workshop configuration. Scope your own
secrets to that exact repository. Continue with step 3 above; do not create a
main-branch Codespace and patch it silently afterward.

### If a key was added or its repository access changed

Stop and start the **same Codespace** after saving the secret. Restarting alone
does not rerun the creation check. In a new terminal, run:

```bash
bash "$(git rev-parse --show-toplevel)/.devcontainer/software-factories-workshop/setup.sh"
```

Wait for `Setup finished` before initializing, training, or chatting. If it still
says `NOT READY`, stop and ask the presenter or the secret's owner. Keep the
existing workspace and the error words, without the key. If you are not ready
by minute 25, raise your hand and pair with a neighbor; share the screen, not
credentials.

## The order of the parts

| Minutes | You do | What to show |
| --- | --- | --- |
| 0–10 | Open Codespaces while the presenter shows the result | Setup status and the four target conversations |
| 10–30 | Create, install, train, and open your Mantle helper | Confirmation, restart, clarification, and refusal |
| 30–50 | Try corrections, cancellation, and different wording | What the helper recorded and what it refused |
| 50–70 | Change one source value, catch it, then restore it | Source check FAIL, followed by restored PASS |
| 70–75 | Break | |
| 75–115 | Connect the practice builder; optionally use a billed Agents session | A labeled proposal, absolute saved path, and SHA-256 |
| 115–140 | Compare the saved bytes and run the four gate controls | One ACCEPT and three REJECT results |
| 140–160 | Record a human approval or refusal | The exact proposal and the reason; no automatic application |
| 160–180 | Presenter preview, discussion, and next steps | A short Studio 2 preview; attendees install nothing |

In today's fresh 4-core test Codespaces, a tester reached the first confirmation
at about 10 minutes and all four conversation checks by about 11 minutes. Those
runs used an existing account and assistance. They are observations, not a
first-time attendee guarantee. The refreshed complete folder still needs its
own cold walkthrough.

## Use one path

- **Attendees:** [the attendee pack](ATTENDEE-PACK.md) contains the commands and
  recovery steps. [Learning checkpoints](LEARNING-CHECKPOINTS.md) help you explain
  the result. [The build contract](BUILD-CONTRACT.md) says what the proposal and
  gate establish.
- **Presenters:** use [the run sheet](RUN-SHEET-DARK-FACTORY.md),
  [facilitator notes](FACILITATOR.md), [table card](FACILITATOR-CARD.md),
  [slides](slides/index.html), [PDF](slides/masterclass-slides.pdf), and
  [presenter notes](slides/PRESENTER-NOTES.md).
- **Source:** [router-helper](router-helper/README.md) contains the helper,
  builder, and gate. The [archive](archive/) preserves older editions;
  those local, travel, and voice routes are outside this session.

Studio 2 is a presenter-only preview, not an attendee setup task. Join the
[Rasa Community](https://info.rasa.com/community/) to hear about its release.
