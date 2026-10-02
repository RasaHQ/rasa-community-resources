# Improver delta

Scores are NVIDIA `quality-check` on **projected** Agent Skills copies.
Native Mantle `skill.md` is not SkillEvaluator input.
`config/mantle.yml` must stay byte-identical after the copy.
Skill-doc length is whitespace word count, not inference tokens.

| Skill | Mode | Baseline quality | Improved quality | Words before | Words after | Constraints preserved | Changes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rasano/banking-faq | failed | 87.5 | 87.5 | 106 | 106 | True | llm rewrite failed schema/noop gate or timed out; original skill kept without heuristic alteration |
| rasano/default-session-start | llm | 86.0 | 86.0 | 76 | 94 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/goodbye | failed | 84.8 | 84.8 | 76 | 76 | True | llm rewrite failed schema/noop gate or timed out; original skill kept without heuristic alteration |
| rasano/human-handoff | llm | 81.8 | 82.5 | 100 | 122 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/intro | llm | 90.0 | 90.8 | 127 | 172 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/list-payees | llm | 90.0 | 90.8 | 87 | 119 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/add-payee | llm | 82.5 | 82.5 | 142 | 164 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/block-card | llm | 79.5 | 81.8 | 279 | 314 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/check-balance | failed | 83.0 | 83.0 | 158 | 158 | True | llm rewrite failed schema/noop gate or timed out; original skill kept without heuristic alteration |
| rasano/remove-payee | llm | 81.8 | 82.5 | 93 | 124 | True | llm writing-for-agents rewrite; llm unslop in same call |
| rasano/transfer-money | llm | 80.8 | 83.0 | 232 | 317 | True | llm writing-for-agents rewrite; llm unslop in same call |
| personalization/default-session-start | llm | 77.8 | 77.8 | 60 | 112 | True | llm writing-for-agents rewrite; llm unslop in same call |
| personalization/view-transactions | llm | 81.8 | 81.8 | 287 | 324 | True | llm writing-for-agents rewrite; llm unslop in same call |
