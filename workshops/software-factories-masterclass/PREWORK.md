# Setup before the workshop

Bring a laptop, headphones and a charger. Work in groups of three or four. One working machine per group is enough.

## Accounts for the voice and live-builder route

- An issued Rasa Developer Edition license (`RASA_LICENSE`). Request it at https://rasa.com/rasa-pro-developer-edition-license-key-request . A submitted form is not an issued license.
- An OpenAI API application key with Agents session read/write and model inference permissions. The official Agents quickstart names `api.agents.read`, `api.agents.write`, and `api.responses.write`. ChatGPT access alone does not establish API access.
- A Deepgram key (`DEEPGRAM_API_KEY`) for speech recognition and synthesis.
- Python 3.12, uv, Git and Make. The existing code-verification labs require macOS. Other participants use the data-only track or join a Mac group. Native Windows launcher support is not established; use a group machine for that route.

Check the account's available credits and enforceable limits before paid work. Call-count and time limits are not a dollar cap. This package has no per-session money cap. Do not retry paid builds in a loop.

## Using this ZIP

Unzip it. Open a terminal in the resulting `software-factories-masterclass` directory. Initialize a local repository so the demo can check that `.env` is untracked and ignored:

```bash
git init
```

This creates local Git metadata only; no GitHub account, commit or push is needed. Do not run `git add .` after entering credentials.

```bash
cd book/ready/ch00/demo
make env
make setup
```

Open the new `.env` in your own editor and fill in the license, OpenAI key and Deepgram key. Anthropic is optional and not required for this workshop. Leave the template committed only with blank values. Then:

```bash
make doctor
```

It prints credential names and readiness, never their values. It does not prove account access or working speech. The facilitator rehearsal checks those. Setup can take several minutes and downloads a substantial dependency tree; do it before arriving.

## No accounts or unsupported machine?

Install Python 3.12. Open `PARTICIPANT-GUIDE.md` and use Track B. You can run a genuine acceptance/recovery exercise with no extra packages. It does not call Mantle, Deepgram or OpenAI; pair for that part of the experience.
