# The complete voice factory: implementation contract

This is the target specification and missing-integration checklist, not a claim that the attached code already implements it.

## The user journey

1. I say: “Build me a voice assistant for my flight to New York. Show the arrival weather and whether I can make my meeting.”
2. The factory assistant asks only for missing requirements, reads back the brief, and gets confirmation before starting paid build work.
3. A visible job shows queued, building, checking and ready, or a specific failure. Conversation remains responsive while the build runs.
4. The system gives me a preview URL only after the exact artifact passes the release checks.
5. I open that assistant and ask about my flight by voice. It answers briefly and updates a visual flight/weather/timeline/currency board.
6. I request a change. The factory builds a candidate, evaluates it independently and either releases a new version or keeps the previous working version.

## Responsibilities

| Component | Responsibility | What it must not imply |
|---|---|---|
| Factory conversation: Mantle + Deepgram | Spoken requirements, clarification, confirmation, status | A voice transcript alone does not establish a complete build |
| Factory MCP service | Submit/status/cancel jobs; bind task to artifact and evidence | MCP itself is neither an evaluator nor a deployment system |
| OpenAI Agents API worker | Managed builder session with explicitly scoped file tools or sandbox | Session completion is not acceptance |
| Independent verifier | Validate task, scope, product behavior and artifact identity | A hidden test suite alone is not a security boundary |
| Release worker | Train/start checked artifact, run smoke checks, preserve rollback | Copying files is not proof the new app is running |
| Generated travel agent: Mantle + Deepgram | User conversation and tool routing | Its prompts do not supply authoritative flight values |
| Source adapters and custom UI | Validated observations, estimates, assumptions, unavailable states | These visual cards are application code, not a built-in Agents API UI feature |

The supplied code includes the travel agent, source MCP tools and a separate builder driver. It lacks a factory conversation skill exposing build jobs and a demonstrated release bridge into a newly launched travel agent.

## Suggested MCP job contract

`submit_build(brief, request_id)` validates a confirmed brief, assigns a durable job ID and returns quickly. `get_build(job_id)` returns the state and safe progress. `cancel_build(job_id)` requests cancellation and never reports cancellation until acknowledged. Names are proposed application interfaces, not vendor APIs.

Allowed transitions: QUEUED → BUILDING → CHECKING → ACCEPTED → RELEASING → READY. Any stage can fail; bounded transient failures may retry. REJECTED means a product requirement failed. NOT_READY means no valid judgment was possible. Cancellation and timeout never become READY.

The job record includes the normalized brief, caller request ID, task digest, base artifact digest, builder session ID, candidate digest, verifier/version, test results, release artifact digest and final URL. Repeated request IDs with the same brief return the original job. A different brief with the same ID is refused.

Only the release worker writes the release record. The builder cannot change task authority, tests, verification results or release policy. A directory copy and file hashes detect some changes; they do not stop arbitrary untrusted code. Run code in an actual isolated worker with no provider keys and a separate protected verifier.

## Acceptance scenarios for the complete demo

| ID | Action / fault | Required observation |
|---|---|---|
| F01 | Speak the brief | Correct transcript, clarification and confirmed normalized task |
| F02 | Start the same request twice | One build job and one billed session, or explicit reconciliation of uncertain submission |
| F03 | Builder finishes | CHECKING, never immediately READY |
| F04 | Candidate changes protected evaluator or asks for secrets | Refusal and preserved previous release |
| F05 | Candidate labels daily FX as live | REJECTED with the violated requirement |
| F06 | Provider fails / worker times out | NOT_READY or FAILED; no successful release claim |
| F07 | Accepted artifact changes before release | Digest mismatch blocks release |
| F08 | Release succeeds | Checked artifact starts; returned URL serves that version; prior version remains recoverable |
| V01 | Ask about flight by voice | Recognized request, audible short answer and matching visual cards |
| V02 | Say a short “yes”; interrupt speech | Confirmation heard; playback stops appropriately; task state preserved |
| V03 | Give an ambiguous flight or date | A clarification question, no invented flight/date |
| V04 | Set transfer to 120 minutes | Timeline changes; selected flight and meeting remain unchanged |
| D01 | Weather source unavailable | Weather unavailable; other cards retained; no stale value labelled current |
| D02 | Position-based arrival estimate | Clearly labelled estimate; no invented airline delay status |
| D03 | Run recorded data | Visible and spoken replay disclosure where relevant |
| R01 | Restart after submission | Job can be recovered without silently repeating side effects |
| R02 | Cancel during build | Cancellation acknowledged and no subsequent release |

## A practical three-hour scope

Use a prepared travel scaffold, not an empty repository. Ask the builder for one visible feature with precise acceptance examples. Once the bridge exists, it can copy the scaffold, implement the feature, run checks and launch the result. This is still an agent building another agent, provided the artifacts and release are real and visible. The workshop should say what the scaffold supplies and what the builder actually changes.

Do not present these scenario descriptions as an automated suite. Each needs an implementation and recorded execution before claiming the full demo is ready.
