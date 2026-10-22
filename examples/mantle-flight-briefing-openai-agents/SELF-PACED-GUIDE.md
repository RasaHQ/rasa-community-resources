# Run, inspect and challenge the travel assistant

Allow 30 to 45 minutes after installation. Use Python 3.12, uv, Git and Make. A Rasa license is required even for scripted text. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested.

## 1. Start with typed, scripted requests

In this example folder, run `make env`, fill only the issued `RASA_LICENSE` in the private `.env`, then run `make setup` and `make doctor`. For a ZIP, first run `git init` here so credential tracking checks work. Keep `.env` ignored and untracked.

Run `make run-scripted` and open http://127.0.0.1:8942/ after readiness. This path chooses tools with code and calls current public sources. It is not an offline replay. For the reproducible recorded exercise, use the workshop's chapter 0 instead.

Type “I'm heading to New York. Which flights are already in the air?” Read the returned options and named suggestion. Type “yes, that one” only if it is the option you intend. Supply the meeting's day and destination-local time. Never use a fixed flight number as evidence that a flight is currently airborne.

**Done when:** four cards are visible, source dates are readable, and you can distinguish observation, estimate, forecast, assumption and daily reference rate. If a source fails, record the unavailable state; do not claim a full successful live briefing.

## 2. Change one assumption

Type “Allow 120 minutes to get into town.” Check that the timeline changes, while your chosen flight and meeting stay the same. Explain why the transfer allowance is not a live traffic prediction.

**Done when:** you can show the before/after allowance and name the data that stayed unchanged.

## 3. Challenge the dialogue

Start a new conversation. Ask for London, then reply “no” if asked for a flight number. The demo should explain that discovery covers selected New York routes, without repeatedly asking the same question or claiming no London flights exist.

In another new conversation, request New York. Decline the suggested flight, then say “yes.” The assistant must ask you to choose explicitly, rather than silently revive the rejected suggestion. Also try “JFK or Newark”: ambiguity should trigger clarification.

**Done when:** write one Given/When/Then example for each behavior, with what you saw. These are evaluation requirements, not claims that an unconstrained live model will always pass.

## 4. Add a live provider only after the baseline works

Read README and LIVE-WORKER before entering additional private keys. `make run` can use available model credentials and may incur cost. The Agents API default is gpt-6-astra. An expected cost range is not a spending cap. Use one bounded attempt and inspect its status before retrying.

Deepgram adds speech input and output. Voice was tested with Deepgram audio files today and failed on the second turn, so type your requests. The microphone path is untested. If you try it, test microphone permission, audible output, a short confirmation and interruption separately. Text success is not a voice pass. Keep the pinned runtime's configuration; the latest Mantle schema is different.

## 5. Apply the factory method

Go to the workshop PARTICIPANT-GUIDE. Write a small change and failure examples before asking the builder. Keep task, attempt and verifier evidence together. The builder may see example tests. It never sees or edits the acceptance tests that decide. A standalone accepted card is not a deployed travel assistant.

For help, share the command, Python version and error sentence. Never share keys or .env. Stop your own launcher with Ctrl-C; do not terminate another participant's processes.
