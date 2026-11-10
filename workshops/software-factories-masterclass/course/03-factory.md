# Let a Mantle agent operate the factory · 85–135 minutes

You have been the factory operator, passing a brief to Codex and reviewing the output. Now give that job’s first step to a Mantle agent named **Travel Factory Studio**. The traveler asks the product for flight information. A developer asks Studio for a new travel agent.

### 1. Read the build contract (10 minutes)

Open [the builder](../factory/build.py) at `propose`. Find `sessions.create`, `get_final_result`, `artifacts.list` and `content`. The hosted OpenAI **Agents API** receives the brief and instructions, runs a hosted session, and exposes its output as an artifact. The Python `openai` client calls that service. The workshop does not use an Agents SDK Runner.

| Boundary | Evidence to keep |
| --- | --- |
| Hosted session finishes | Session ID. Final text alone supplies no file. |
| Artifact listing contains the expected path | `/workspace/outputs/agent.json` and artifact ID |
| Content download finishes | Saved candidate bytes and local SHA-256 |
| Human approves the matching candidate | Separate Mantle project containing the generated skill and its allowed tools |

**Predict:** the session says “done” and saves only `notes.txt`. Can Studio produce a travel agent from that run? **Answer:** the builder selects only the contracted artifact path. Without it, stop and report a missing candidate.

**Delivery puzzle.** The hosted session finished and the builder wrote “ready,” but the artifact list contains only `notes.txt`. Which of those observations proves a travel desk was built? Inspect the path filter in the builder: without the expected `agent.json`, there are no candidate bytes to approve.

### 2. Ask Studio to build (20 minutes)

Stop the product Inspector with **Ctrl+C**, then run `bash desk inspect studio`. End the traveler call. Use `bash desk url` from a second terminal, open Inspector, click **Start voice conversation**, and speak this brief:

> Build a four-tool travel desk for someone flying from Bergen to Oslo. Ask for a flight number before giving arrival weather and convert a USD budget to NOK.

Studio should ask for permission to start a billed hosted session. Listen for the spoken confirmation. Say **“No”** and inspect the events. No build should run. Ask again only if you intend to run the live exercise and have Agents API and model access. Say **“Yes, start the build”** once. Inspect the factory tool call and receipt. Studio invokes the existing Python builder in its own locked environment. The proposed traveler agent lives in a new directory after review.

**Alternative entry point:** `bash desk propose hosted "Build a Bergen to Oslo travel desk with all four tools."` exercises the same hosted builder from a terminal. Use one paid entry point per build. If a result is uncertain, inspect the existing run and its session information before considering a retry.

### 3. Operate the handoff (20 minutes)

Review the candidate's instructions for airport ambiguity, dates and missing evidence. Compare its name and skill with the Codex candidate. Run `bash desk approve runs/YOUR_HOSTED_RUN_ID builds/studio-desk`. Stop Studio, then run `bash desk inspect builds/studio-desk`. Start a new voice conversation with that generated agent. Ask aloud for Heathrow weather, listen to the reply, then ask for a currency conversion in the same call. Verify both tool results. A successful build ends with a usable product, separate from Studio.

**If live access is unavailable**, use `bash desk propose sample`, approve that returned path and train the sample-built project. Trace the four API calls in source, mark hosted generation pending and continue with the trip. Keep mode, session ID where applicable, receipt hash, output directory and observed conversation in your notes.

[OpenAI hosted Agents API quickstart](https://developers.openai.com/api/docs/guides/agents-api/quickstart)
