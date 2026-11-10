# V7 review handoff — based on PRs 146 and 147

**Candidate, not a deployed or approved release.** Baseline: main `47497e7c861abd8fd2cd76ddd30a35467ee52e83`. The supplied v6 workshop matches that commit byte for byte. V7 starts from this baseline, not v5.

## The rejection was correct

V5 was built against an earlier uploaded snapshot and would revert chapter 0 to dev5 if copied over post-PR146 main. Do not apply it. PR146's 3.21.0 migration and PR147's documentation are retained here. The operator reports a fresh-clone licensed qualification of PR146; this review neither repeats nor contradicts that external run.

The earlier cleanup result was **one failing test in a single 94-test run**, not one failure in 94 repeated shutdown runs and not a measured failure rate.

## Runtime boundaries preserved

| Component | Rasa Pro | Core | Selection / speech |
|---|---|---|---|
| Workshop chapter 0 | 3.21.0 | 0.36.2 | agent.yml orchestrator.model_group; deepgram_flux ASR |
| Standalone example | 3.21.0.dev5 | 0.36.3 | Its existing version-specific configuration |

All pyproject.toml, uv.lock, requirements.txt, integrations.yml and voice_config.py files in both included trees are byte-identical to the baseline. The workshop's migrated agent.yml and doctor code are retained. No downgrade, lock regeneration, broad folder replacement from v5 or new runtime dependency is included.

## Proposed changes

1. **Launcher fixes:** wait for descendants within the existing TERM/KILL deadlines; refuse a process group that outlives them. Accept “yes, that one” using the same validated suggestion. Includes regression tests in each runtime copy. The existing guide continues to use “that one”; it does not depend on this optional punctuation fix.
2. **Teaching and documentation:** explanation checkpoints; browser-readable book; corrected nested chapter-0 setup/model-selection instructions; precise API/client wording; distinguish historical audit counts from current candidate results; put the agenda second and align Track B restrictions on the slide. Preserve the v6 responsive design and the three-hour/125-minute group-work schedule.
3. **Source-failure instructions:** reconcile the skill's unconditional access claim with the workshop's already-honest persona; correct the same inconsistency in the standalone example. This affects live-model instructions and is a separate reviewable patch. No live-model behavior is certified by the scripted tests.

The review bundle supplies separate patches for these three groups. Apply selected patches on a branch after checking the base; do not overwrite the frozen class checkout. Teaching and slide changes travel together so their numbering stays consistent.

## Executed for this candidate

Both environments were installed from the baseline's committed locks with `uv sync --frozen`, into fresh external environment directories. No lock was changed and no extra test dependency was installed.

| Check | Result | Limit |
|---|---|---|
| Chapter 0 focused suite | 107 passed | Real 3.21.0 engine with scripted provider, MCP/hooks, voice schemas, public-source input contracts, traveller, credentials and launcher controls |
| Standalone focused suite | 87 passed | Actual dev5/Core 0.36.3 environment; traveller, credentials and launcher controls |
| Desktop slides | 29 slides, no layout failures at 1600×900 and 1280×720 | Navigation/notes pass; zero remote asset requests; PDF rebuilt |
| Responsive slides | No text overflow at 390×844, 768×1024 and 1024×768 | Mobile reading layout; projection and print retain desktop composition |
| Version preservation | Protected runtime files match baseline hashes | Exact list in the review bundle baseline.json |

The 194 passing focused tests are not a complete repository test run, a new licensed Mac rehearsal, a paid Agents session or a voice qualification. No credentials were requested. The automated build/release bridge remains unfinished. The freeze report names 16:30 UTC on 22 October, which is 17:30 London time; this artifact does not change that freeze or publish anything.

## Reviewer acceptance checklist

- Verify the base commit and runtime-file hashes before applying patches.
- Review each patch's own scope, rather than treating the ZIP as an instruction to replace main.
- Re-run the focused suites in the intended environments; retain their versions and results.
- For the launcher fix, exercise start/stop on the actual Mac after the freeze.
- For live instruction changes, rehearse a source outage with the live provider before making new behavior claims.
- Approve independently. This handoff provides evidence, not approval on behalf of the reviewers.

## Beginner teaching revision

The operator supplied a new README after v6. This candidate adopts its travel-first explanation, with capability claims narrowed to what the exercises support. The 29-slide deck introduces agents, tools, Mantle, Deepgram, the Agents API and software factories before the labs. Slides 5–18 take 20 minutes; a matching beginner primer supports independent study. The 125 minutes of lab and networking time remain unchanged.
