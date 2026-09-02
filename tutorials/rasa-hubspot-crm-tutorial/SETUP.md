# Setup, one step at a time

Follow this top to bottom. Every step ends with something you can run to check
it worked, so you never get three steps deep before finding out something is
wrong.

If you only want to see the agent run, **do steps 0 and 1 and stop** — the
project ships a mock CRM and needs no HubSpot account at all. Steps 2 to 4 are
for connecting it to real HubSpot.

---

## Step 0 — Install the tools

You need Python 3.11 or 3.12, and [uv](https://docs.astral.sh/uv/).

```bash
python3 --version          # want 3.11.x or 3.12.x
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then, from this folder:

```bash
make install
```

**Check it worked:** the command finishes without an error and a `.venv/`
folder appears.

---

## Step 1 — Run it against the mock CRM

You need two keys here, and neither is HubSpot.

| Key | Where to get it |
| --- | --- |
| `RASA_LICENSE` | [Free Developer Edition key](https://rasa.com/rasa-pro-developer-edition-license-key-request) — arrives by email |
| `OPENAI_API_KEY` | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |

Create your env file and paste them in:

```bash
make env          # copies .env.example to .env
```

Open `.env` in an editor. Fill in the two values. **Leave the two HubSpot lines
exactly as they are** — they point at the bundled mock.

Now open **two terminals**, both in this folder.

Terminal 1 — the fake CRM:

```bash
make mock
```

Leave it running. It prints `mock HubSpot CRM listening on http://127.0.0.1:8787`.

Terminal 2 — the agent:

```bash
make crm-check     # should print three green ticks
make train
make chat
```

**Check it worked:** say `hi, it's dana.okafor@example.com`, then
`what tickets do I have open?`. You should hear about invoice 4471.

If `make crm-check` complains it cannot reach the CRM, terminal 1 is not
running.

---

## Step 2 — Create a HubSpot private app

You need to be a **super admin** on the HubSpot account. If you are not, ask
whoever owns your portal — nobody else can see this menu.

1. Sign in to HubSpot
2. In the top navigation, go to **Development**
3. In the left sidebar, click **Legacy apps**
4. Top right, click **Create legacy app**
5. Choose **Private** in the dialog
6. On the **Basic Info** tab, give it a name — `Rasa tutorial` is fine
7. Click the **Scopes** tab
8. Click **Add new scope** and tick these:

| Scope | Why this agent needs it |
| --- | --- |
| `crm.objects.contacts.read` | look the caller up by email |
| `tickets` | read the tickets on their account |
| `crm.objects.notes.write` | write the call summary to their timeline |

9. Top right, click **Create app**, then **Continue creating**

> **If you cannot find `crm.objects.notes.write`** — it is not offered on every
> plan, and several people have hit this. Tick `crm.objects.contacts.write`
> instead: on those accounts the engagement APIs fall back to the contacts
> scope. Step 4 tells you which one you ended up with, so you do not have to
> guess.

**Check it worked:** the app appears under **Development → Legacy apps**.

---

## Step 3 — Copy the access token

1. **Development → Legacy apps**
2. Click your app's name
3. Click the **Auth** tab
4. Click **Show token**, then **Copy**

Now paste it into `.env`, and switch the base URL over to real HubSpot:

```bash
HUBSPOT_ACCESS_TOKEN=<paste the token here>
# HUBSPOT_BASE_URL=http://127.0.0.1:8787      <- comment this line out
```

Commenting out `HUBSPOT_BASE_URL` is what makes the agent talk to
`https://api.hubapi.com` instead of the mock.

> `.env` is in `.gitignore`. Never commit it, and never paste the token into a
> chat, an issue, or a pull request. If it leaks, delete the app in HubSpot —
> that revokes the token immediately.

**Check it worked:** step 4.

---

## Step 4 — Prove the token works

```bash
make crm-check EMAIL=you@example.com
```

Use a real email that exists in your HubSpot as a contact — your own is
easiest.

A good result looks like this:

```text
  base url  https://api.hubapi.com  (real HubSpot)
  token     set, 61 chars

  ✓ read contacts              Ada Lovelace id=12345
  ✓ read tickets               1 found
  ✓ write notes                created note 67890 (delete it from the timeline)

  All good. Run: make train, then make chat
```

That last check **writes a real note** to that contact's timeline, marked as a
test. Delete it afterwards.

### If a row fails

| What you see | What to do |
| --- | --- |
| `HubSpot rejected the token itself` | The token is wrong, or was regenerated. Copy it again (step 3). |
| `The token is valid but the app is missing a scope` | Go back to step 2 and tick the scope named in the message. Scope changes apply immediately. |
| `crm_unreachable` / `crm_timeout` | Network or proxy problem. |
| `reachable, no match for …` | The token works. That email is just not a contact in your portal — try another. |

---

## Step 5 — Run the agent against real HubSpot

```bash
make train
make chat
```

Use your own email when it asks. Everything the agent tells you now comes from
your real portal.

---

## Getting unstuck

**`make crm-check` says NOT SET but the token is in `.env`.**
You edited `.env.example` instead of `.env`. They are different files.

**The agent says it cannot reach the CRM, but `make crm-check` passes.**
`make train` needs re-running after a `.env` change — the agent reads its
configuration at start-up.

**"I am not a super admin."**
You cannot create a private app. Ask your HubSpot admin to do steps 2 and 3 and
send you the token — they never need to see this code.

**I want to go back to the mock.**
Uncomment `HUBSPOT_BASE_URL` in `.env`, run `make mock` in a second terminal.
Nothing else changes.
