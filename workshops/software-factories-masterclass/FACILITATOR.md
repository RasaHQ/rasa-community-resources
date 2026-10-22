# Facilitator rehearsal and teaching notes

The timing authority is `RUN-SHEET.md`. Slide-by-slide cues are in `slides/PRESENTER-NOTES.md`.

## Rehearsal sequence

1. Unzip into a fresh directory. Follow `PREWORK.md` exactly, including local Git initialization if using this ZIP. Do not use an existing virtual environment as evidence of clean setup.
2. Run the travel demo in explicitly scripted replay mode. Confirm four REPLAY cards and that changing the transfer allowance changes only the timeline. This tests the fallback, not voice or model reasoning.
3. Optional extension rehearsal only (voice failed on the second turn in today's audio-file test, so the class types): with your license and keys, start `make run`. Confirm the selected Mantle provider and the separate Agents API worker. Make a spoken request, a short “yes”, an interruption and a transfer-time correction. Check both what is spoken and what appears on the cards. A silent transition to text is a fallback, not a voice pass.
4. In a fresh chapter 5 folder on macOS, run the scripted builder and then one live Agents API build with the default gpt-6-astra (or an explicitly approved alternative) and expected spend. Inspect native status and protected decision. Test one bad candidate in chapter 6 and local integration in chapter 7.
5. Check `BUILD-CONTRACT.md`. Unless the spoken build request actually starts a bounded build, passes gates, launches the checked travel artifact and returns its URL, mark the complete voice factory **not yet demonstrated**. Do not fill this gap with narration.
6. Test the data-only fallback on a second laptop using Python 3.12. This route does not need API keys or a Rasa license.
7. Open the slides offline at projector resolution. Keep the participant guide open in another tab. Prepare an actual recording of the live demo if available; this pack contains no new recording.

## Group facilitation

Use groups of three or four, formed around an available machine rather than operating-system preference. The driver runs commands. The requirements owner writes the brief and examples. The evaluator predicts what should fail and checks evidence. An observer records surprises and asks another table for a counterexample. Rotate roles after the break.

Use a two-minute intervention: ask for the last successful checkpoint, read the exact error, offer the documented recovery, then let the group continue. A participant who cannot install can still author acceptance cases and evaluate results. Do not spend the workshop debugging credentials publicly.

Ask groups to explain why a test failed before editing anything. A missing dependency is NOT_READY, not a rejected product. An accepted candidate needs integration and user-facing checks before release.

## Demonstration modes

- **LIVE:** a provider actually ran in this demonstration. Identify which provider and which part.
- **SCRIPTED:** teaching code chose actions. It can still call real tools.
- **REPLAY:** recorded input data. Its date is not the current date.
- **ILLUSTRATION:** a slide or mockup explains a design. It is not an application screenshot.

## What to leave out of the main session

The old card-blocking exercise, the SDK reviewer stub, Wilson intervals, forged test-runner output and historical prerelease compiler behavior are optional follow-up topics. They should not displace participants building and evaluating the travel assistant. Keep historical findings tied to their exact original engine pin.
