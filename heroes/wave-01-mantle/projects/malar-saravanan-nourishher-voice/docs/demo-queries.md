# Demo queries — exercising every capability

Example utterances that walk through each part of NourishHer. Type them in
`make inspect` (voice or text), the web UI (`make api` + `make ui`), or the
REST endpoint (see the README). Every example is fictional — no real person,
clinic, or product is referenced.

Each conversation is keyed by a `sender` id, so a **new id is a new person**
with an empty profile. Reuse the same id to build up history across turns.

## One guided first session

Run these in order as a single person (one `sender` id). This is the natural
path a real user takes, and it is the order the condition-aware skills need —
they only unlock once a profile exists (see "Condition gating" below).

| # | You say | What should happen | Skill |
|---|---|---|---|
| 1 | "hi" | Warm intro, offers to build a profile | `intro` |
| 2 | "My name is Aya and I want steadier energy through the day" | Captures name + goal, begins onboarding | `intake_profile` |
| 3 | "I mostly eat South Indian vegetarian food, no eggs, and I have about 20 minutes to cook on weeknights" | Captures cuisine, diet, dislikes, cooking time | `intake_profile` |
| 4 | "I also have PCOS and hypothyroidism, and I take levothyroxine" | Records both conditions + medication, reads the profile back to confirm | `intake_profile` |
| 5 | "yes that's right" | Saves the profile; condition skills now unlock | `intake_profile` |
| 6 | "I had two idlis with sambar and a coffee for breakfast" | Logs the meal verbatim, confirms | `meal_logging` |
| 7 | "how much protein and iron is in 100 grams of chana dal?" | Live USDA lookup rendered as macro/micro tables with %DV, "per 100 g" basis stated | `nutrition_qna` |
| 8 | "what should I eat for PCOS?" | Condition-aware, non-prescriptive guidance grounded in the reference docs | `pcos_nutrition` |
| 9 | "plan two vegetarian dinners for this week and a grocery list" | One primary + one alternative, plus a shopping list | `meal_planning` |
| 10 | "what have I eaten today?" | Reads back the logged meals | `meal_history` |
| 11 | "I keep skipping lunch and then overeat at night" | Supportive, non-judgemental coaching + one next step | `coaching_checkin` |
| 12 | "actually I'm not vegetarian anymore" | Updates the stored preference without re-running intake | `update_profile` |
| 13 | "thanks, bye" | Closes warmly | `goodbye` |

## Capability reference

| Capability | Example utterance | Prerequisite |
|---|---|---|
| Orientation | "what can you help me with?" | none |
| Onboarding / profile | "set up my profile" | none |
| Update a preference | "change my cooking time to 40 minutes" | profile exists |
| Natural meal logging | "I snacked on almonds and an apple" | none |
| Meal history | "what did I eat this week?" | some logged meals |
| Behavioural summary | "am I eating enough protein lately?" | some logged meals |
| Meal planning | "give me a high-protein vegetarian lunch idea" | profile helps, not required |
| Grocery list | "make a grocery list for that plan" | a saved plan |
| Nutrition Q&A (live USDA) | "how much calcium is in 100 g of tofu?" | none |
| PCOS guidance | "what foods help with PCOS?" | intake done + PCOS declared |
| Hypothyroidism guidance | "what should I eat with hypothyroidism?" | intake done + hypothyroidism declared |
| Type 2 diabetes guidance | "how should I eat for type 2 diabetes?" | intake done + diabetes declared |
| Fertility / preconception | "what should I eat while trying to conceive?" | intake done + fertility declared |
| Professional referral | "can you recommend a dietitian?" | none |

## Safety escalation (verbatim, never LLM-generated)

Each red-flag phrase triggers a fixed, spoken-verbatim hand-off — no diagnosis,
no medication advice. These work at any point in a conversation.

| You say | Red-flag type |
|---|---|
| "I feel really dizzy and shaky and haven't eaten all day" | hypoglycemia |
| "my heart is racing, I'm sweating and shaking and very anxious" | thyroid crisis |
| "I've had heavy bleeding for two weeks straight" | menstrual pattern |
| "I've been skipping meals for days to lose weight fast" | disordered eating |
| "should I stop taking my levothyroxine?" | medication change |
| "do I have PCOS?" | diagnosis request |
| "can this diet cure my thyroid disease?" | cure claim |
| "I have severe chest pain right now" | urgent symptom |

## Condition gating

The four condition skills (`pcos_nutrition`, `hypothyroidism_nutrition`,
`diabetes_nutrition`, `fertility_nutrition`) are gated on
`session.project.profile_intake_complete == True` **and** the matching
`has_<condition>` flag. Those flags are only written when a person completes
`intake_profile` and declares the condition. Ask a condition question *before*
onboarding and the general `nutrition_qna` skill answers instead, deferring
condition-specific claims. This is deliberate: the assistant never assumes a
person has a condition they have not stated.
