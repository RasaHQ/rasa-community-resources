# Build and check a router helper in GitHub Codespaces

**New York workshop — Tuesday, November 3, 2026, 3:00–6:00 PM Eastern.**
A hands-on session by Rod Rivera for developers who want to connect an agent to
tools, inspect a proposed code change, and decide whether to accept it.

You build a small Rasa Mantle helper that asks before recording a simulated
router restart. Then you connect a builder, inspect its saved proposal, and
accept or reject it with a separate check. The exercise contacts no router.
Its final result is a recorded review decision, with nothing installed or
applied automatically. Attendees use Mantle throughout.

## Start here at minute 0 · From a browser tab to your first router check

Nothing needs to be set up before the workshop. You need a browser, your own
GitHub account, your own free Rasa Developer Edition key, and your own OpenAI
API key. Request or retrieve the keys at minute 0 if needed. Model usage is
billed to your OpenAI account; the practice builder starts no Agents session.

> [!TIP]
> **Your first conversation.** Ask **Restart my router**, wait for the
> confirmation question, then answer **Yes**. In the Inspector, look for
> `command_sent: REBOOT` in the tool result.

### A. Sign in to GitHub

A Codespace is a computer that GitHub runs for you. Its editor and terminal open
in your browser. Use a personal GitHub account that has Codespaces available and
enough allowance for a four-core machine. Keep this page open in a separate tab.

### B. Collect two values

If your workshop host supplied either value, use it in the matching row.
Otherwise follow the link in that row.

| Name to enter in GitHub | Where to get the value | What uses it |
| --- | --- | --- |
| `RASA_LICENSE` | [Request a Rasa Developer Edition license](https://rasa.com/rasa-pro-developer-edition-license-key-request). The form's confirmation page is not the key; copy the entire license string you receive. | Rasa Mantle uses it to run the helper. |
| `OPENAI_API_KEY` | [Open your OpenAI project's API keys](https://platform.openai.com/api-keys), choose **Create new secret key**, and copy the value while it is visible. Use a project with API billing and model access. | The helper uses it when you chat. ChatGPT subscriptions and API billing are separate. |

The first file check runs inside the Codespace and spends no model call.
Chatting with the helper uses the OpenAI API. The practice builder copies a
supplied sample file. Generating a new file with the optional billed builder
needs Agents API access and can incur a separate charge.

### C. Save both values as personal Codespaces secrets

1. Open [GitHub → Settings → Codespaces](https://github.com/settings/codespaces).
   Scroll to **Codespaces secrets** and choose **New secret**.
2. In **Name**, enter `RASA_LICENSE`. In **Value**, paste the license string.
   Under **Repository access**, select **RasaHQ/rasa-community-resources**
   and save.
3. Repeat for `OPENAI_API_KEY`, pasting the OpenAI key. If either name already
   exists, edit its repository access to include the workshop repository, and
   keep any other repository access you still use.
4. Check that both names appear in the list. GitHub supplies their values to
   your Codespace. No fork, local installation or `.env` file is needed. Never
   put a key in source, a command, a shared log, or chat.

If GitHub does not offer the repository in your settings, use the matching
secret fields on the creation form in step D instead.

### D. Open the workshop

**[Open the workshop in GitHub Codespaces →](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/software-factories-workshop/devcontainer.json)**

On GitHub's creation form, check that the repository is
**RasaHQ/rasa-community-resources**, the configuration is **New York workshop:
Rasa Mantle**, and the machine has **at least 4 cores**. Fill in any secret the
form asks for, then choose **Create codespace**. The editor opens while Python,
uv and the two locked environments are prepared; you do not install them on your
laptop.

Already created this workshop's Codespace? [Open it from Your
codespaces](https://github.com/codespaces) to keep your files.

### Your first win: check the restart command

When the terminal shows a line beginning **`Setup finished`**, installation is
done. An available editor alone does not mean setup finished. In the editor,
choose **Terminal → New Terminal**, copy one box at a time and press Enter.

Check that GitHub supplied both values without printing either:

```bash
for name in RASA_LICENSE OPENAI_API_KEY; do if [ -n "${!name:-}" ]; then echo "$name present"; else echo "$name missing"; fi; done
```

Then run the source-file check on the completed example in your workspace:

```bash
ROUTER="$(git rev-parse --show-toplevel)/workshops/software-factories-masterclass/router-helper"
python3 "$ROUTER/check_helper.py" "$ROUTER/mantle/skills/router_restart/tools.py"
```

You should see **`PASS: a restart records REBOOT`**. You just checked the
command in a real Python file without spending a model call. Next you build your
own helper and find out whether it waits for permission before it uses that
command: continue with **Your router helper** in the
[attendee pack](ATTENDEE-PACK.md#your-router-helper-minutes-1030), or follow the
[browser tutorial](https://rasa.community/library/tutorials/software-factory/).

The setup check verifies license handling and the presence of the model key; the
helper conversation checks model access. A present key still needs billing and
permission for the model.

**Reviewing an unmerged change:** use the repository and branch named in the
review handoff. Open that branch on GitHub, choose **Code → Codespaces → New
with options**, and select the same workshop configuration. Scope your own
secrets to that exact repository. Continue from **Your first win** above; do not create a
main-branch Codespace and patch it silently afterward.

### If a key was added or its repository access changed

Fix the secret and its repository access in step C. Then, in [Your
codespaces](https://github.com/codespaces), use the **…** menu to stop the
**same Codespace** and open it again. Restarting alone does not rerun the
creation check. In a new terminal, run:

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
