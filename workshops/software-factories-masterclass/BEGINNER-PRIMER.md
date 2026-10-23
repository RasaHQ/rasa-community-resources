# Start here: from a travel question to a software factory

Allow 15 to 20 minutes. You need no previous knowledge of these products.

## What makes this an AI agent?

It can use tools to help answer a question.

<div class="contrast"><div><h2>You ask</h2><blockquote>“Will I make my 6 pm meeting?”</blockquote><p>A language model interprets the request.</p></div><div><h2>The application acts</h2><p>It collects missing details, calls permitted tools and uses their results in its answer.</p></div></div>

## A tool brings in information.

A tool is a function the agent can ask the application to run.

<table><tr><td>Question</td><td>Tool result</td><td>Visible answer</td></tr><tr><td>When does my flight land?</td><td>Flight status and arrival time</td><td>Flight card</td></tr><tr><td>What happens after landing?</td><td>Arrival time + your transfer allowance</td><td>Arrival timeline</td></tr><tr><td>What will I need there?</td><td>Weather and exchange-rate sources</td><td>Weather and currency cards</td></tr></table>

## Rasa Mantle runs the conversation.

Mantle is the framework used to build our travel agent.

<div class="contrast"><div><h2>It coordinates the work</h2><p>Keep track of the conversation.<br>Choose a skill and call its tools.<br>Apply instructions and constraints.</p></div><div><h2>We supply the application</h2><p>Travel instructions and tools.<br>Connections to data sources.<br>The code that draws the four cards.</p></div></div>

## Follow one turn through Mantle.

The conversation gathers what the tools need.

<table><tr><td>Traveler</td><td>“Will I make my meeting?”</td></tr><tr><td>Conversation</td><td>Ask for the flight and meeting time if missing.</td></tr><tr><td>Briefing tool</td><td>Fetch the available sources; calculate the timeline.</td></tr><tr><td>Travel application</td><td>Show the answer and cards, including source labels.</td></tr></table>

## Deepgram adds a speech interface.

Speech changes how a request enters and leaves the conversation.

<table><tr><td>Speech to text</td><td>Your audio becomes words the agent can process.</td></tr><tr><td>Conversation</td><td>Mantle works with the request and tool results.</td></tr><tr><td>Text to speech</td><td>The answer becomes audio you can hear.</td></tr><tr><td>Today’s route</td><td>Type. Recorded-audio testing failed on turn two; microphone use is untested.</td></tr></table>

## The coding agent has a different job.

The travel agent answers a traveler. The builder changes software.

<div class="contrast"><div><h2>Travel agent</h2><blockquote>“Will I make my meeting?”</blockquote><p>Uses travel tools to answer.<br>Does not need permission to edit code.</p></div><div><h2>Builder</h2><blockquote>“Show three currency rows.”</blockquote><p>Proposes a change to product files.<br>Must not control the deciding tests.</p></div></div>

## The OpenAI Agents API runs a builder session.

An API is an interface one program uses to ask another service to do work.

<table><tr><td>Our application sends</td><td>A task, agent configuration and execution environment.</td></tr><tr><td>The service runs</td><td>A model session that can use configured tools.</td></tr><tr><td>Our application receives</td><td>Progress and results, then checks the proposed files.</td></tr><tr><td>Our application still owns</td><td>Permissions, independent checks, recovery and release decisions.</td></tr></table>

## Agents API and Agents SDK are different.

This workshop uses the service through a Python client.

<table><tr><td>Agents API</td><td>The OpenAI service managing the session.</td></tr><tr><td>OpenAI Python client</td><td>Code our application uses to call that service.</td></tr><tr><td>Agents SDK</td><td>A separate framework; not the implementation taught here.</td></tr><tr><td>MCP</td><td>A protocol for exposing tools to agents; not a builder or a dashboard.</td></tr></table>

## What is a software factory?

A repeatable process from a written request to a checked change.

<table><tr><td>1 · Specify</td><td>“Display three currency rows, with the reference date.”</td></tr><tr><td>2 · Build</td><td>A coding agent produces an attempt.</td></tr><tr><td>3 · Check</td><td>Independent acceptance tests compare behavior with the request.</td></tr><tr><td>4 · Decide</td><td>Accept or reject; integrate only an accepted attempt.</td></tr></table>

## What makes a factory “dark”?

Routine building and checking run without someone reviewing every line.

<div class="contrast"><div><h2>People set the rules</h2><p>What may change?<br>What must pass?<br>When should work stop for help?</p></div><div><h2>Machines follow the rules</h2><p>Build within that scope.<br>Run independent checks.<br>Keep evidence for the decision.</p></div></div>

## Try the rule before the code.

Request: display exactly three currency rows.

<table><tr><td>Attempt output</td><td>Decision</td><td>Reason</td></tr><tr><td>Four rows</td><td>REJECT</td><td>The requested limit was not respected.</td></tr><tr><td>Three rows, reference date present</td><td>Check all remaining requirements</td><td>One visible success is not the whole suite.</td></tr><tr><td>All required checks pass</td><td>ACCEPT</td><td>This attempt meets the specified checks.</td></tr></table>

## The builder cannot grade its own homework.

An independent verifier checks the proposed artifact.

<div class="boundary"><div class="build-zone"><label>BUILDER WORKSPACE</label><h2>Task + product files</h2><p>Allowed changes only<br>Development tests available</p></div><div class="boundary-line">attempt</div><div class="verify-zone"><label>VERIFIER WORKSPACE</label><h2>Protected acceptance</h2><p>Independent result<br>Task and artifact fingerprints (short codes made from the files)</p></div></div><p class="caption">The builder may see example tests. It never sees or edits the acceptance tests that decide.</p>

## A completed session still needs a decision.

A setup failure is different from a bad product.

<div class="panels"><article><span class="num">01</span><h2>ACCEPT</h2><p>The attempt passed the specified checks. Release checks still follow.</p></article><article><span class="num">02</span><h2>REJECT</h2><p>A product requirement failed. Change the proposal and try again.</p></article><article><span class="num">03</span><h2>NOT_READY (could not run)</h2><p>A dependency, account or verifier failed. No product verdict exists.</p></article></div>

## Check your understanding with a neighbor.

Explain the process without using the word “AI”.

<div class="contrast"><div><h2>Who does what?</h2><p>Who answers the traveler?<br>Who changes product files?<br>Who decides whether a change passes?</p></div><div><h2>What if the builder says “done”?</h2><p>What evidence would you ask for?<br>Which failure should stop the run?<br>Who handles an exception?</p></div></div>

## A few terms in plain language

A **framework** supplies reusable structure for an application. A Mantle **skill** groups instructions and tools for a particular job. **Conversation state** is information retained across turns, such as the selected flight.

A **session** is a managed run of an agent’s work. An **execution environment** is where its tools run. **MCP** means Model Context Protocol: an agreed way to expose tools to agents. It does not render the cards or decide whether code should be released.

An **attempt** is a proposed set of changed files. **Integration** brings an accepted change into the local product. An **artifact fingerprint** is a value computed from file contents: it helps detect a mismatch, but does not prevent someone from reading or editing a file.

The optional live builder uses the Agents API. The default builder exercise is repeatable and needs no OpenAI key. Neither route turns the travel agent itself into a coding agent.

## Check before you continue

Explain the difference between answering a traveler and changing the application. Why is the builder saying “done” not evidence of acceptance?

Expected explanation: Mantle coordinates the travel conversation; tools supply information. A separate builder proposes product files. Independent acceptance tests decide whether those files meet the request. People define the policy and handle exceptions.

Continue with the [participant guide](PARTICIPANT-GUIDE.md).

## Product references

- [Rasa Mantle](https://mantle.rasa.com/)
- [OpenAI Agents API](https://developers.openai.com/api/docs/guides/agents-api/overview)
- [Deepgram](https://developers.deepgram.com/docs/overview)
