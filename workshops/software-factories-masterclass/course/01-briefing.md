# Your first travel briefing · 0–30 minutes

**Traveler:** “I land at Heathrow. What should I pack, and how much is $200 in pounds?” Start with the two parts you can answer before knowing the flight number.

### 1. Meet the tools before the model

In a new workshop terminal, run:

```bash
bash desk data weather LHR
bash desk data fx USD GBP 200
```

Read the airport, forecast hour, temperature in Celsius and rain probability. Read the base and quote currencies, rate, converted amount and reference date. A forecast for the current hour helps with “what’s it like now?” To answer “when I land,” the tool needs the arrival time. A daily reference rate is useful for budgeting; the card issuer may charge a different rate.

**Try a flight before minute 30.** Ask for the remaining OSL → BGO schedule now:

```bash
bash desk data flights OSL BGO
```

Choose a flight number from the returned board and use `bash desk data status FLIGHT_NUMBER` with that actual number. Compare the flight’s estimated and scheduled arrival. If the provider returns no matches, keep the coverage note in your answer. The board needs no key.

<details><summary>Worked example from a tool run on 2 November 2026</summary>

The FX tool returned `base: USD`, `quote: GBP`, `amount: 200`, `rate: 0.74628` and `reference_date: 2026-11-02`. Multiply 200 by 0.74628 and round to two decimals: **£149.26**. This is an example from the underlying Mantle tool. When you run it, use the date and rate in your own response.

The weather tool returned **9.1 °C** for **22:00 local time at LHR**. That supports a statement about that forecast hour. It does not answer a question about a flight arriving tomorrow morning.

</details>

**Before the next call:** run `bash desk data fx USD GBP 100`. Predict the result from your $200 receipt, then check the rate date and rounding. In the voice exercise, find those same fields in Inspector.

### 2. Build a working starting point

After the creation log says **Travel factory dependencies ready**, run:

```bash
bash desk doctor
bash desk starter
bash desk inspect builds/starter
```

The first command reports presence without printing values. The second creates a Mantle project from the supplied two-tool starter. The third trains it and starts Inspector. Leave this terminal running. If the starter already exists, skip its creation and inspect that folder again.

### 3. Ask a real question

Keep the server running in Terminal 1. Choose **Terminal → New Terminal** and run `bash desk url`. Open the printed **HTTPS** link in its own tab. This opens the private Rasa Inspector. If GitHub shows **Continue**, continue with the same signed-in GitHub account.

1. Connect your headset or turn on your microphone and speakers. In Inspector find the waveform button labeled **Start voice conversation**. Click it.
2. When your browser asks to use the microphone, choose **Allow** for this Inspector site. Speak into your own device: **“What is the weather at London Heathrow right now?”** Pause and listen for a spoken answer.
3. **Stay in the same call.** Ask: **“And how much is two hundred US dollars in British pounds?”** Listen for the amount and rate date. This second turn checks that the agent is still listening after its first reply.
4. Open **Inspect** and compare the recognized questions and the `destination_weather` and `convert_currency` tool results with what you heard. End the call with **Stop voice conversation** before closing the tab.

| Voice symptom | What to check |
| --- | --- |
| No mic permission prompt or transcript | Open the HTTPS Inspector tab directly. In the browser’s site permissions, allow its microphone, select the right input device, reload and start a new call. |
| Transcript but no spoken reply | Check the tab is unmuted and the correct output device is selected. Check the server terminal for speech synthesis or Deepgram account errors. |
| First turn succeeds and the second stalls | Save the turn number, transcript and server error category without credentials. Mark the two-turn voice test incomplete. Typed chat can isolate a tool problem. |

| If you see | Do this |
| --- | --- |
| A missing secret | Fix its repository access in personal Codespaces settings, stop and reopen this same Codespace, then rerun `bash desk doctor`. |
| Missing environment or Codex executable after creation failed | In the workshop terminal run `bash ../../.devcontainer/travel-factory/install.sh`. |
| Empty browser page | Wait for the server-ready message. Run `bash desk url` in the second terminal. Keep port 5010 private. |
| API or model denial | Keep the error category, check project billing and model access. Run the provider exercise directly and mark the chat pending. |

**Minute 30 checkpoint.** Explain which tool supplied each number. Show one tool result alongside what the traveler saw. If only the command-line tools ran, record that separately. The next chapter adds the flight information missing from this first agent.
