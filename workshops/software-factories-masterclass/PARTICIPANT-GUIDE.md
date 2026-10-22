# Your group builds and checks a travel assistant

You have 110 minutes of lab time, with a 15-minute break to meet another group. Work at your own pace. Your most useful result is a small change that you can explain, reject when wrong, and trace to the version you ran.

The destination is a **voice factory assistant** that takes a product brief and builds a **travel assistant**. The supplied code currently demonstrates the travel assistant and factory separately. You will improve and evaluate those components; the full voice-triggered build/release bridge is an extension described in `BUILD-CONTRACT.md`.

## Before the lab (5 minutes)

Open a terminal in the `software-factories-masterclass` folder. After a clone, that is `rasa-community-resources/workshops/software-factories-masterclass`. After unzipping, it is the unzipped folder:

```bash
export PACK="$PWD"
python3 --version
```

Use Python 3.12. Chapter 0 runs on Rasa Pro 3.21.0, tested on 22 October. The standalone example in `examples/` stays on 3.21.0.dev5 today. `PACK` always means this folder (the `software-factories-masterclass` folder); keep the terminal open. In a new terminal, set `PACK` again to the full path. Read `PREWORK.md` if you have not installed dependencies.

Choose your route:

| Route | You need | You will run |
|---|---|---|
| A: travel scaffold and coding factory | A Mac for code gates; Python 3.12, uv, Git, Make; issued Rasa license; provider keys only for optional live runs | Travel assistant, Agents API builder, rejection and local integration |
| B: data-only factory | Any machine with Python 3.12 only (3.13 and 3.14 stop with NOT_READY); commands below use a POSIX shell, and Windows is untested | Acceptance, rejection, retry limits and duplicate suppression, with scripted proposals |

If setup is still blocking you after ten minutes, use B and pair with an A group for the typed travel demonstration. A file-presence check is not evidence that an agent works.

Assign driver, requirements owner and evaluator. A fourth person records evidence. Swap after the break.

## Shared checkpoint 1: a brief with examples (10 minutes)

Write `group-brief.md` in your own work folder. Use this request:

> Build a voice travel assistant. I tell it my flight and meeting time. It shows the flight, arrival weather and a timeline, then tells me whether my plan fits. It asks when details are missing. I can change my transfer allowance without starting over.

Choose one small extension: limit the currency card to two currencies; clarify the transfer allowance; or improve the unavailable-weather state. The supplied coding exercise implements the currency limit. Other choices need new tests and are extension work.

Write four examples **before** asking a builder:

| Given / when | Expected result |
|---|---|
| Four currency rates, limit 2 | Exactly two rows; daily reference date visible; no claim of live trading prices |
| Forecast provider fails | Weather unavailable with a reason; flight and timeline remain usable |
| Meeting at 18:00, landing estimate 17:00, transfer allowance 90 minutes | Arrival at 18:30; 30 minutes late under these assumptions |
| User says “make that two hours” | Change the transfer allowance only; preserve chosen flight and meeting |

Add a fifth example from your own experience. Decide what would count as NOT_READY (for example, an account cannot access the API) rather than REJECT (the output violates the request).

**Checkpoint:** another person can predict pass/fail from your examples without reading proposed code.

## Track A, checkpoint 2: the travel experience (15 minutes)

From your prepared package:

```bash
cd "$PACK/book/ready/ch00/demo"
make doctor
```

For today's checkpoint, use typed requests and recorded sources. Run:

```bash
BRIEFING_RECORDED=1 make run-scripted
```

Open http://127.0.0.1:8942/ after the launcher reports ready. Type the three recorded prompts below. Voice is optional extension work and has not been tested end to end.

Record what you typed, what changed on screen, which sources supplied the values, and the SCRIPTED / REPLAY mode. Optional voice testing belongs after the core exercise; test audible output, short answers and interruptions separately.

The arrival is a position-based estimate, not an airline ETA. The transfer is an assumption, not live traffic. The currency card uses reference rates. The custom card renderer is application code, not automatic Mantle or Agents API UI generation.

Type `United 1162 to EWR`, then `The 6 pm meeting tomorrow.`, then `Allow 30 minutes to get into town.` In this recording “tomorrow” is 23 October 2026. In another terminal, from `book/ready/ch00`, run:

```bash
python3 check_demo.py --recorded --transfer-minutes 30
```

Expected: `ch00 OK`. Label the result SCRIPTED / REPLAY. Keep the live voice checkpoint incomplete.

**Checkpoint:** four labeled cards, correct timeline revision, and a clear record of whether you tested live speech, live text or replay.

## Track A, checkpoint 3: one bounded builder (25 minutes)

Use a fresh folder so earlier evidence stays intact:

```bash
export WORK="$(mktemp -d "${TMPDIR:-/tmp}/factory-group.XXXXXX")"
cp -R "$PACK/book/ready/ch05/." "$WORK/"
cd "$WORK"
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install -r requirements.txt
python build.py tasks/b-limit-currencies.json attempts/first --scripted
python check_build.py attempts/first
```

Expected: ACCEPT and an explicit SCRIPTED label. The completion check then prints `NOT DONE` and exits 1: the supplied limit is still 2, and this check requires your own change to 1 or 3. This is the expected starting result, not a setup failure. Now edit only the task's `limit` to 1 or 3:

```bash
python - <<'EDIT'
import json
from pathlib import Path
p = Path('tasks/b-limit-currencies.json')
t = json.loads(p.read_text()); t['limit'] = 3
p.write_text(json.dumps(t, indent=2) + '\n')
EDIT
```

First finish offline with the edited task:

```bash
python build.py tasks/b-limit-currencies.json attempts/changed --scripted
python check_build.py attempts/changed
```

Expected: ACCEPT, then `ch05 OK`. You now have a complete checkpoint even without API access.

For an optional real builder, provide `OPENAI_API_KEY` privately to this process environment. The demo's `.env` is not automatically read here. Use a password manager or secure local terminal prompt; never put the key in the task or share it. Choose an account-approved Agents model. The supplied default example is `gpt-6-astra`; a model working in Mantle does not prove it is available to an Agents session.

```bash
printf 'Approved model: '; IFS= read -r MODEL
printf 'Expected lower cost in USD cents: '; IFS= read -r MIN
printf 'Expected upper cost in USD cents: '; IFS= read -r MAX
python build.py tasks/b-limit-currencies.json attempts/mine --live \
  --model "$MODEL" --expected-cost-cents-min "$MIN" --expected-cost-cents-max "$MAX"
python check_build.py attempts/mine
```

The cost range is an estimate, not an enforced monetary cap. The driver limits tools and elapsed time. Use one paid attempt, inspect its result, and decide whether a second is worthwhile. If live access fails, use a fresh `attempts/offline` with `--scripted` and record the limitation.

Optional evidence viewer, in the same work folder:

```bash
python factory_engine/factory_console.py runs/mine/run --port 8943
```

Open http://127.0.0.1:8943/ . It is read-only. Inspect task, file actions, diff and verdict. A session finishing successfully is not enough: the independent checker must accept the output.

**Checkpoint:** the exact exported files match your chosen limit and protected decision. Keep the task and evidence together. This exercise builds a small Python card component; it does not create or restart the voice agent.

## Networking break (15 minutes)

Meet a different group. Ask what their agent got wrong or what their tests would miss. Bring one new failure case back to your table. Rotate roles.

## Track A, checkpoint 4: a useful rejection (20 minutes)

Create a fresh chapter 6 folder:

```bash
export GATES="$(mktemp -d "${TMPDIR:-/tmp}/factory-gates.XXXXXX")"
cp -R "$PACK/book/ready/ch06/." "$GATES/"
cd "$GATES"
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
python run_a6.py tasks/a6-market-watchlist.json candidates/market-good
python run_a6.py tasks/a6-market-watchlist.json candidates/market-shows-live
```

Expected: first ACCEPT, second REJECT. Predict the second result before running it. Find the check that refuses daily rates labeled as live. Try the provided `market-invents-on-failure` attempt too. Do not weaken the test to obtain green output.

**Checkpoint:** name the violated requirement and the rejecting check. Distinguish this controlled example from a model's measured failure rate.

## Track A, checkpoint 5: integration and handoff (25 minutes)

This checkpoint is a separate local card integration. It is not automatic release into the live travel agent.

```bash
export RELEASE="$(mktemp -d "${TMPDIR:-/tmp}/factory-release.XXXXXX")"
cp -R "$PACK/book/ready/ch07/." "$RELEASE/"
cd "$RELEASE"
uv venv --python 3.12 .venv
. .venv/bin/activate
uv pip install zeocore==0.35.6 httpx==0.28.1
python set_limit.py 3
python integrate.py --record-base
python integrate.py tasks/b-limit-currencies.json attempts/mine
python show_card.py --offline
```

Open `card.html`. Expected: three currencies and an explicit sample-data label. `set_limit.py` generates a scripted attempt for this chapter. Do not claim it is your earlier live-generated artifact. To carry that exact artifact, follow chapter 5's transfer instructions and require compatible protected-suite fingerprints.

Repeat integration. Expected: refusal because the base changed. Explain why an attempt tested against yesterday's product cannot simply replace today's product.

For the complete target architecture, read `BUILD-CONTRACT.md` and identify which steps your group has evidence for. Finish `group-handoff.md` with the fields below.

## Track B: a runnable factory without provider accounts

This route uses supplied scripted proposals and validates JSON as data. It does not execute generated Python and does not claim the same isolation guarantees as the macOS code route.

Python 3.12 only. Python 3.13 and 3.14 stop with NOT_READY, which means the check could not run. Windows is untested. Run `python3 --version` first. If it doesn't print 3.12, use your 3.12 interpreter in place of `python3` below.

From the package root, in a POSIX terminal:

```bash
export RECOVERY="$(mktemp -d "${TMPDIR:-/tmp}/factory-recovery.XXXXXX")"
cp -R "$PACK/book/ready/ch08/." "$RECOVERY/"
cd "$RECOVERY"
python3 lesson.py see
python3 set_request.py 3
python3 lesson.py build
python3 lesson.py measure
python3 lesson.py recover
python3 lesson.py recover
python3 lesson.py check
```

**Windows is untested.** Suggested PowerShell adaptation (not verified): copy `book/ready/ch08` to a new folder in File Explorer, open that folder in PowerShell, and run the same seven Python commands using `py -3.12` in place of `python3`.

Expected: accepted proposal; rejected original two-attempt baseline; one simulated crash followed by an accepted retry; duplicate call executes zero further attempts; final `ch08 OK`. The two measured cases are selected teaching cases, not a success-rate benchmark.

Then repeat in another fresh folder with `set_request.py 1`. Recovery should escalate after the first controlled crash (exit code 4), while `lesson.py check` still passes because escalation is the requested result.

The builder may see example tests. It never sees or edits the acceptance tests that decide.

Use the remaining time to design the travel acceptance scenarios, inspect `BUILD-CONTRACT.md`, and pair with a travel-demo group. Ask where their job records survive a restart, and what prevents two clicks from launching two builds.

## Final handoff (10 minutes within Lab B)

Write these fields in `group-handoff.md`:

- Requirement and chosen limit or retry allowance.
- Runtime versions and mode: LIVE, SCRIPTED or REPLAY.
- Accepted artifact path and evidence path.
- One deliberately rejected result and the check that rejected it.
- Integration result; separate voice/browser result if performed.
- One remaining limitation and the next test you would add.

For the closing demo, spend 30 seconds on the requirement, 60 on the rejection and result, and 30 on the limitation. Show the output rather than the builder's success message.

## Troubleshooting

| Symptom | Meaning and next step |
|---|---|
| “could not run: this check needs macOS” | The verifier did not judge the product. Use B or a Mac group; do not remove the sandbox check. |
| Wrong Python version | Use Python 3.12; chapter 8 deliberately rejects other runtimes. |
| `ModuleNotFoundError` | Activate that chapter's environment and install its exact requirements. The worker and Mantle environments are separate. |
| `.env` not ignored / Git check fails | Initialize Git at the package root; retain the demo's `.gitignore`; keep `.env` untracked. |
| API permission or model error | Check the account with its owner; preserve the failed run; use a fresh scripted attempt. |
| Voice switches to text | Continue the exercise in text and record voice as incomplete. |
| Port occupied | Stop your own earlier process with Ctrl-C or `make stop`. |
| Attempt already exists | Choose a new attempt name. |
| Source unavailable | Show the reason; use labeled replay for the exercise. |
| Fingerprints differ | Use a fresh supplied chapter; do not repin tests merely to accept an attempt. |

Further reading: the individual chapters explain each component in more detail. Their older historical experiments remain tied to their own pins. The current technical corrections and evidence are in `TECHNICAL-AUDIT.md`.
