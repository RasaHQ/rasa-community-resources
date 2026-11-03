# Build the full travel desk with Codex · 30–75 minutes

**Traveler:** “That forecast is for now. Can you check when my flight actually arrives?” The starter has no flight-status reader. Give the new agent a way to discover the arrival airport and time before it requests the forecast.

### 1. Inspect a Mantle project (10 minutes)

Open `builds/starter/agent.yml`, then `skills/travel_briefing/skill.md` and `tools.py` underneath that project. The first sets identity and rules. The skill tells Mantle when to route a question and which tools to call. The Python functions return provider data in a `ToolResult`. Open [the shared readers](../travel_data.py) and predict which field changes when an estimated arrival becomes available.

**Before you write the brief:** compare “use the first matching flight” with “ask for the date when two records match.” For each, predict whether a weather call can occur before the traveler answers. Keep your prediction for the two-date rehearsal in the final lab.

### 2. Give Codex the build brief (15 minutes)

Use a **new workshop terminal**. To authenticate Codex with the saved workshop project key, run `bash desk login`. This sends the key to the login command over standard input. Running Codex with this account can incur model charges. Then run:

```bash
bash desk propose codex "Build a travel desk for Oslo to Bergen. Check flight status before arrival weather. Give me tonight’s other departures and convert my dollar budget into Norwegian kroner. Ask for missing airports and distinguish scheduled from estimated arrival."
```

Codex writes the agent specification in a fresh run directory. The specification contains the agent name, routing description, skill instructions and selected tools. The workshop compiler turns that specification into a runnable Mantle project using reviewed provider functions. Read the resulting instructions: is it clear what happens when two flights share a number or when a provider is unavailable?

**Without Codex access:** `bash desk propose sample` copies the authored example through the same build steps. Label the result as a sample. Later, rerun this section with Codex and compare the generated skill.

### 3. Review, build and try it (20 minutes)

Open the printed candidate path in the editor. Require these four capabilities: `status`, `weather`, `fx`, `flights`. Read the instructions as if you were handling an uncertain arrival. If they are unsatisfactory, keep the candidate for comparison and request a revision. Each new generation can be billed.

Copy the **directory** containing that candidate into the following command, replacing the placeholder. Approval compares the candidate with its receipt and builds a new project. It refuses to overwrite an existing output.

```bash
bash desk approve runs/YOUR_RUN_ID builds/codex-desk
```

Stop the starter Inspector with **Ctrl+C** in its own terminal. Run `bash desk inspect builds/codex-desk` from the workshop terminal. Open the private Inspector again, click **Start voice conversation**, and ask aloud “Which flights are scheduled from Oslo to Bergen tonight?” Compare its result with `bash desk data flights OSL BGO` from a second terminal. If the board is unavailable, the agent should say so.

### Improve the actual Mantle skill with Codex

Once the generated desk works, ask a harder question: “I might fly into London or Paris. Which weather did you check?” Use Codex to change what the agent asks before calling a tool. Start from a **copy** of the working project.

```bash
cp -R builds/codex-desk builds/clarifying-desk
cd builds/clarifying-desk
"$HOME/.local/node_modules/.bin/codex"
```

Give Codex this instruction:

> Edit only skills/travel_briefing/skill.md. For an ambiguous destination or a flight number shared by several records, ask one clarification question using the returned dates or airport codes. After the traveler chooses, use the selected record’s estimated or scheduled arrival for weather. Preserve all four tool references. Show me the diff and explain which question should trigger each branch.

Exit Codex with `/quit`. Return to the workshop with `cd ../..`. Compare the two skill files using `diff -u builds/codex-desk/skills/travel_briefing/skill.md builds/clarifying-desk/skills/travel_briefing/skill.md`. Differences are expected. Stop the old Inspector and run `bash desk inspect builds/clarifying-desk`. Try the same ambiguous question again. **Success:** a clarification precedes a destination-specific lookup; an unambiguous request still reaches the tool. If time is short, resume this iteration during home practice.

**Checkpoint.** Find all four tool references in the generated skill. In the flight result, identify the origin-local date, provider coverage and scheduled departure. The board can list schedules; it cannot promise a seat.

**Break, minutes 75–85.** Save the run ID and generated directory. You can reopen the same Codespace and train this project again without calling Codex again.

If you want to compare files before spending a model call, open the [finished reference agent](../reference/finished-agent/agent.yml) and its [travel skill](../reference/finished-agent/skills/travel_briefing/skill.md). Your generated project uses the same layout.
