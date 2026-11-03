# Brief a traveler, then change the product · 135–180 minutes

### 1. Follow a single journey (15 minutes)

Open the approved four-tool agent in Inspector, start a voice conversation and ask aloud “I’m leaving Oslo for Bergen tonight. Which flights are scheduled, what will the weather be when I land, and how much is $200 in Norwegian kroner?” If the board returns several flights, choose an actual flight number and date from the result. If none are returned, ask for an independent forecast at an explicit time and the currency conversion.

| Traveler needs | Inspect this tool | Check before trusting the answer |
| --- | --- | --- |
| Flights tonight | `tonight_departures` | Oslo’s local date. Remaining scheduled departures from 18:00 up to midnight. Only the returned provider page was searched. |
| One flight’s arrival | `flight_status` | Match number, date, origin and destination. Prefer the estimated arrival if present. Multiple matches need clarification. |
| Landing weather | `destination_weather` | The requested airport and forecast hour must match the flight’s arrival. A missing or out-of-range time needs an explanation. |
| Spending money | `convert_currency` | Base USD, quote NOK, requested amount, rate date and result. A reference rate is distinct from a card transaction. |

Try “Can you guarantee me a seat?” A schedule reader has no inventory or booking authority. A useful reply can still tell the traveler which flight to check with the airline.

### Run the two-date case on your own agent

**Traveler:** “I’m on ZZ201 to Bergen. Will I need a coat when I land?” The classroom board has two records under that number. Write down the first thing you expect to hear. If the desk immediately gives a temperature, what did it assume?

1. In the workshop terminal, run `bash desk case status ZZ201`. This uses the same reader as the product with **invented provider responses**. On 3 November the scheduled arrival is 19:20 Bergen time and the estimate is 20:10. On 4 November only the 19:20 schedule is available.
2. Predict both weather inputs before checking either. Run:

```bash
bash desk case weather BGO 2026-11-03T20:10:00+01:00
bash desk case weather BGO 2026-11-04T19:20:00+01:00
```

3. Stop the running Inspector with Ctrl+C. From the workshop folder run `bash desk rehearse builds/studio-desk`, substituting your approved four-tool project. Start a voice call and ask the ZZ201 question. If it asks which date, say “November third, 2026.” Repeat in a fresh call for November fourth. Inspect the arguments as well as the spoken answers. The flight and weather data are simulated; Mantle conversations and Deepgram audio still require the usual credentials.
4. Compare your observations with the table. A direct reader check tests the data handling. Only a conversation shows whether the generated skill asked for clarification at the right time.

| Traveler's choice | Expected tool sequence | Forecast in the fixture |
| --- | --- | --- |
| Date still unknown | Status lookup, then clarification; weather waits | No forecast yet |
| November 3 | Request Bergen weather for the estimated 20:10 arrival | 20:00 hour, 4 °C, 80% rain probability |
| November 4 | Request Bergen weather for the scheduled 19:20 arrival | 19:00 hour, 7 °C, 30% rain probability |

If the desk gives 8 °C for November 3, inspect the timestamp. That is the earlier, scheduled hour. Ask Codex to repair the skill, then repeat the same call against the same data. Keep the before-and-after tool events. To return to public providers, stop Inspector and start `bash desk inspect builds/studio-desk` normally.

### Check a provider failure if time permits

Run `bash desk test`. Open [the tests](../tests/test_travel.py). Find the flight that departs at 23:30 UTC but still belongs to the next local date at Oslo. Why would filtering by the UTC date lose or misclassify departures?

Try `bash desk data weather ZZZ` and `bash desk data fx USD GBP -5`. Inspect the structured unavailable result. Try `bash desk data flights JFK LHR` to see how the desk handles an unsupported route. Ask why “the board is unavailable” and “there are no flights tonight” would lead a traveler to different decisions.

### 3. Record a release decision (8 minutes)

Write a note with the build mode (Codex, hosted, or sample), candidate path and hash, which Mantle project you trained, and one observed tool result. State which providers answered live and which you only exercised with fixtures. If the agent offered a seat, invented a flight, or substituted current conditions for missing arrival weather, defer approval and issue a new brief.

### 4. Continue at home (7 minutes now, then at your own pace)

Save the note, stop the Inspector with Ctrl+C, then use **… → Stop codespace** in [Your Codespaces](https://github.com/codespaces). To resume, reopen that workspace and run `bash desk inspect builds/codex-desk` or the name you approved. This reuses the project without starting another paid build.

**Extension A · Improve the conversation (20 minutes).** Ask Codex for another four-tool desk that responds in Spanish and asks for the travel date when a flight number has multiple records. Review, approve into a new folder, and try the same trip in Spanish. Compare the inspected arguments and the answer with your earlier result.

**Extension B · Implement another destination with Codex (30 minutes).** Open `travel_data.py` and the tests. In a workshop terminal run `"$HOME/.local/node_modules/.bin/codex"` and give it this brief:

> Add Tokyo Haneda (HND) to the supported airport catalog. Use verified airport coordinates, Asia/Tokyo and JPY. Update the factory’s airport guidance to match. Write an offline test proving a forecast hour renders in Tokyo local time and a test for a departure near midnight. Run the suite and show the diff.

Review the changes, rerun `bash desk test`, and generate a **new** product directory. The compiler copies the readers into each product, so earlier builds keep their original behavior. Use the provider CLI and Inspector to compare HND weather and a USD-to-JPY conversion.

**Extension C · Improve flight coverage (45 minutes).** Extend the board reader to a third Avinor airport. Add its airport metadata and a test for a route with no remaining departures. Keep coverage explicit.
