# Rasa Heroes skill evaluation

```text
Author:        Arash, Rasa Heroes eval pipeline
Wave:          wave-01-mantle
Assessed on:   2026-09-20
Assessed by:   eval pipeline, rasa-skill-eval
Verified with: rasa-pro 3.20.0.dev6 pin, Python 3.11+, uv, NVIDIA SkillEvaluator
Audience:      Rasa Heroes and Mantle skill authors
Time:          skill-eval plus optional agent-eval
```

See the filled run REPORT.md for the standalone write-up.

## Metrics

| Layer | Metric | What it is | Baseline | Improved | Delta |
| --- | --- | --- | --- | --- | --- |
| T1 quality | overall 0–100 | Offline Agent Skills style linter on **projected** copies (improver pairs) | 83.6 | 87.1 | +3.43 |
| T1 quality | correctness | Quality-check correctness dimension | 81.5 | 81.5 | +0.00 |
| T1 quality | discoverability | Quality-check discoverability dimension | 92.3 | 92.3 | +0.00 |
| T1 quality | reliability | Quality-check reliability dimension | 73.1 | 73.1 | +0.00 |
| T1 quality | efficiency | Quality-check efficiency dimension | 91.5 | 95.4 | +3.85 |
| T1 rubric | weighted 0–100 | LLM judge of skill docs (projected copies) | 65.6 | 67.5 | +1.92 |
| T2 | similarity (personalization) | Overlap inside the projected collection | 0 | n/a | n/a |
| T2 | similarity (rasano) | Overlap inside the projected collection | 14 | n/a | n/a |
| Mantle | TSR (weighted) | Weighted sum of routing / tools / memory / confirmation / safety | 0.27 | 0.42 | +0.15 |
| Mantle | TSR (strict) | Fraction of scenario-runs where every applicable assertion passed | 0.12 | 0.10 | -0.02 |
| Mantle | tokens/task | Prompt+completion tokens when the provider reports usage | 51 | 117 | +65.33 |
| DeepEval | task completion | Judge on tracker transcripts (secondary to TSR) | 0.35 | 0.47 | +0.12 |
| DeepEval | tool correctness | Judge evaluation of tool choice and arguments | 0.13 | 0.15 | +0.02 |
| DeepEval | answer relevancy | Judge evaluation of assistant response relevancy | 0.73 | 0.87 | +0.14 |
| DeepEval | GEval tool correctness | GEval LLM judge of tool choice and safety | 0.12 | 0.21 | +0.09 |

#### NVIDIA Rubric Criteria Breakdown

NVIDIA `rubric-eval` assesses documentation quality across qualitative criteria using LLM-as-a-judge.

| Skill / Arm | Criterion | Score |
| --- | --- | --- |
| `rasano/banking-faq` | description_clarity | 7.0 |
| `rasano/banking-faq` | documentation_completeness | 5.0 |
| `rasano/banking-faq` | error_handling_quality | 8.0 |
| `rasano/banking-faq` | example_quality | 4.0 |
| `rasano/banking-faq` | instruction_clarity | 8.0 |
| `rasano/banking-faq` | professional_tone | 8.0 |
| `rasano/banking-faq` | scope_definition | 8.0 |
| `rasano/banking-faq` | trigger_simulation | 7.0 |
| `rasano/banking-faq` | workflow_completeness | 8.0 |
| `rasano/default-session-start` | description_clarity | 6.0 |
| `rasano/default-session-start` | documentation_completeness | 4.0 |
| `rasano/default-session-start` | error_handling_quality | 0.0 |
| `rasano/default-session-start` | example_quality | 0.0 |
| `rasano/default-session-start` | instruction_clarity | 7.0 |
| `rasano/default-session-start` | professional_tone | 8.0 |
| `rasano/default-session-start` | scope_definition | 7.0 |
| `rasano/default-session-start` | trigger_simulation | 4.0 |
| `rasano/default-session-start` | workflow_completeness | 7.0 |
| `rasano/goodbye` | description_clarity | 8.0 |
| `rasano/goodbye` | documentation_completeness | 4.0 |
| `rasano/goodbye` | error_handling_quality | 2.0 |
| `rasano/goodbye` | example_quality | 2.0 |
| `rasano/goodbye` | instruction_clarity | 8.0 |
| `rasano/goodbye` | professional_tone | 7.0 |
| `rasano/goodbye` | scope_definition | 8.0 |
| `rasano/goodbye` | trigger_simulation | 7.0 |
| `rasano/goodbye` | workflow_completeness | 8.0 |
| `rasano/human-handoff` | description_clarity | 9.0 |
| `rasano/human-handoff` | documentation_completeness | 7.0 |
| `rasano/human-handoff` | error_handling_quality | 2.0 |
| `rasano/human-handoff` | example_quality | 2.0 |
| `rasano/human-handoff` | instruction_clarity | 8.0 |
| `rasano/human-handoff` | professional_tone | 8.0 |
| `rasano/human-handoff` | scope_definition | 8.0 |
| `rasano/human-handoff` | trigger_simulation | 8.0 |
| `rasano/human-handoff` | workflow_completeness | 9.0 |
| `rasano/intro` | description_clarity | 7.0 |
| `rasano/intro` | documentation_completeness | 5.0 |
| `rasano/intro` | error_handling_quality | 0.0 |
| `rasano/intro` | example_quality | 3.0 |
| `rasano/intro` | instruction_clarity | 8.0 |
| `rasano/intro` | professional_tone | 8.0 |
| `rasano/intro` | scope_definition | 7.0 |
| `rasano/intro` | trigger_simulation | 6.0 |
| `rasano/intro` | workflow_completeness | 8.0 |
| `rasano/list-payees` | description_clarity | 9.0 |
| `rasano/list-payees` | documentation_completeness | 3.0 |
| `rasano/list-payees` | error_handling_quality | 2.0 |
| `rasano/list-payees` | example_quality | 1.0 |
| `rasano/list-payees` | instruction_clarity | 7.0 |
| `rasano/list-payees` | professional_tone | 8.0 |
| `rasano/list-payees` | scope_definition | 8.0 |
| `rasano/list-payees` | trigger_simulation | 8.0 |
| `rasano/list-payees` | workflow_completeness | 5.0 |
| `rasano/banking-faq#improved` | description_clarity | 8.0 |
| `rasano/banking-faq#improved` | documentation_completeness | 5.0 |
| `rasano/banking-faq#improved` | error_handling_quality | 7.0 |
| `rasano/banking-faq#improved` | example_quality | 3.0 |
| `rasano/banking-faq#improved` | instruction_clarity | 9.0 |
| `rasano/banking-faq#improved` | professional_tone | 8.0 |
| `rasano/banking-faq#improved` | scope_definition | 7.0 |
| `rasano/banking-faq#improved` | trigger_simulation | 7.0 |
| `rasano/banking-faq#improved` | workflow_completeness | 8.0 |
| `rasano/default-session-start#improved` | description_clarity | 8.0 |
| `rasano/default-session-start#improved` | documentation_completeness | 5.0 |
| `rasano/default-session-start#improved` | error_handling_quality | 2.0 |
| `rasano/default-session-start#improved` | example_quality | 2.0 |
| `rasano/default-session-start#improved` | instruction_clarity | 8.0 |
| `rasano/default-session-start#improved` | professional_tone | 8.0 |
| `rasano/default-session-start#improved` | scope_definition | 8.0 |
| `rasano/default-session-start#improved` | trigger_simulation | 4.0 |
| `rasano/default-session-start#improved` | workflow_completeness | 7.0 |
| `rasano/goodbye#improved` | description_clarity | 8.0 |
| `rasano/goodbye#improved` | documentation_completeness | 5.0 |
| `rasano/goodbye#improved` | error_handling_quality | 2.0 |
| `rasano/goodbye#improved` | example_quality | 2.0 |
| `rasano/goodbye#improved` | instruction_clarity | 8.0 |
| `rasano/goodbye#improved` | professional_tone | 8.0 |
| `rasano/goodbye#improved` | scope_definition | 8.0 |
| `rasano/goodbye#improved` | trigger_simulation | 7.0 |
| `rasano/goodbye#improved` | workflow_completeness | 8.0 |
| `rasano/human-handoff#improved` | description_clarity | 8.0 |
| `rasano/human-handoff#improved` | documentation_completeness | 7.0 |
| `rasano/human-handoff#improved` | error_handling_quality | 2.0 |
| `rasano/human-handoff#improved` | example_quality | 2.0 |
| `rasano/human-handoff#improved` | instruction_clarity | 8.0 |
| `rasano/human-handoff#improved` | professional_tone | 6.0 |
| `rasano/human-handoff#improved` | scope_definition | 8.0 |
| `rasano/human-handoff#improved` | trigger_simulation | 8.0 |
| `rasano/human-handoff#improved` | workflow_completeness | 7.0 |
| `rasano/intro#improved` | description_clarity | 8.0 |
| `rasano/intro#improved` | documentation_completeness | 5.0 |
| `rasano/intro#improved` | error_handling_quality | 3.0 |
| `rasano/intro#improved` | example_quality | 3.0 |
| `rasano/intro#improved` | instruction_clarity | 8.0 |
| `rasano/intro#improved` | professional_tone | 8.0 |
| `rasano/intro#improved` | scope_definition | 8.0 |
| `rasano/intro#improved` | trigger_simulation | 8.0 |
| `rasano/intro#improved` | workflow_completeness | 7.0 |
| `rasano/list-payees#improved` | description_clarity | 8.0 |
| `rasano/list-payees#improved` | documentation_completeness | 4.0 |
| `rasano/list-payees#improved` | error_handling_quality | 2.0 |
| `rasano/list-payees#improved` | example_quality | 2.0 |
| `rasano/list-payees#improved` | instruction_clarity | 7.0 |
| `rasano/list-payees#improved` | professional_tone | 7.0 |
| `rasano/list-payees#improved` | scope_definition | 8.0 |
| `rasano/list-payees#improved` | trigger_simulation | 7.0 |
| `rasano/list-payees#improved` | workflow_completeness | 6.0 |
| `rasano/add-payee#improved` | description_clarity | 9.0 |
| `rasano/add-payee#improved` | documentation_completeness | 7.0 |
| `rasano/add-payee#improved` | error_handling_quality | 3.0 |
| `rasano/add-payee#improved` | example_quality | 2.0 |
| `rasano/add-payee#improved` | instruction_clarity | 8.0 |
| `rasano/add-payee#improved` | professional_tone | 8.0 |
| `rasano/add-payee#improved` | scope_definition | 8.0 |
| `rasano/add-payee#improved` | trigger_simulation | 8.0 |
| `rasano/add-payee#improved` | workflow_completeness | 7.0 |
| `rasano/add-payee` | description_clarity | 8.0 |
| `rasano/add-payee` | documentation_completeness | 7.0 |
| `rasano/add-payee` | error_handling_quality | 4.0 |
| `rasano/add-payee` | example_quality | 2.0 |
| `rasano/add-payee` | instruction_clarity | 8.0 |
| `rasano/add-payee` | professional_tone | 8.0 |
| `rasano/add-payee` | scope_definition | 8.0 |
| `rasano/add-payee` | trigger_simulation | 5.0 |
| `rasano/add-payee` | workflow_completeness | 7.0 |
| `rasano/block-card` | description_clarity | 9.0 |
| `rasano/block-card` | documentation_completeness | 8.0 |
| `rasano/block-card` | error_handling_quality | 6.0 |
| `rasano/block-card` | example_quality | 5.0 |
| `rasano/block-card` | instruction_clarity | 9.0 |
| `rasano/block-card` | professional_tone | 9.0 |
| `rasano/block-card` | scope_definition | 8.0 |
| `rasano/block-card` | trigger_simulation | 8.0 |
| `rasano/block-card` | workflow_completeness | 9.0 |
| `rasano/block-card#improved` | description_clarity | 9.0 |
| `rasano/block-card#improved` | documentation_completeness | 8.0 |
| `rasano/block-card#improved` | error_handling_quality | 6.0 |
| `rasano/block-card#improved` | example_quality | 5.0 |
| `rasano/block-card#improved` | instruction_clarity | 9.0 |
| `rasano/block-card#improved` | professional_tone | 9.0 |
| `rasano/block-card#improved` | scope_definition | 8.0 |
| `rasano/block-card#improved` | trigger_simulation | 8.0 |
| `rasano/block-card#improved` | workflow_completeness | 9.0 |
| `rasano/check-balance` | description_clarity | 9.0 |
| `rasano/check-balance` | documentation_completeness | 8.0 |
| `rasano/check-balance` | error_handling_quality | 8.0 |
| `rasano/check-balance` | example_quality | 5.0 |
| `rasano/check-balance` | instruction_clarity | 9.0 |
| `rasano/check-balance` | professional_tone | 9.0 |
| `rasano/check-balance` | scope_definition | 8.0 |
| `rasano/check-balance` | trigger_simulation | 6.0 |
| `rasano/check-balance` | workflow_completeness | 9.0 |
| `rasano/check-balance#improved` | description_clarity | 8.0 |
| `rasano/check-balance#improved` | documentation_completeness | 8.0 |
| `rasano/check-balance#improved` | error_handling_quality | 8.0 |
| `rasano/check-balance#improved` | example_quality | 5.0 |
| `rasano/check-balance#improved` | instruction_clarity | 9.0 |
| `rasano/check-balance#improved` | professional_tone | 9.0 |
| `rasano/check-balance#improved` | scope_definition | 8.0 |
| `rasano/check-balance#improved` | trigger_simulation | 6.0 |
| `rasano/check-balance#improved` | workflow_completeness | 9.0 |
| `rasano/remove-payee` | description_clarity | 8.0 |
| `rasano/remove-payee` | documentation_completeness | 6.0 |
| `rasano/remove-payee` | error_handling_quality | 3.0 |
| `rasano/remove-payee` | example_quality | 2.0 |
| `rasano/remove-payee` | instruction_clarity | 8.0 |
| `rasano/remove-payee` | professional_tone | 8.0 |
| `rasano/remove-payee` | scope_definition | 8.0 |
| `rasano/remove-payee` | trigger_simulation | 8.0 |
| `rasano/remove-payee` | workflow_completeness | 6.0 |
| `rasano/remove-payee#improved` | description_clarity | 8.0 |
| `rasano/remove-payee#improved` | documentation_completeness | 7.0 |
| `rasano/remove-payee#improved` | error_handling_quality | 4.0 |
| `rasano/remove-payee#improved` | example_quality | 2.0 |
| `rasano/remove-payee#improved` | instruction_clarity | 8.0 |
| `rasano/remove-payee#improved` | professional_tone | 9.0 |
| `rasano/remove-payee#improved` | scope_definition | 8.0 |
| `rasano/remove-payee#improved` | trigger_simulation | 4.0 |
| `rasano/remove-payee#improved` | workflow_completeness | 7.0 |
| `rasano/transfer-money` | description_clarity | 9.0 |
| `rasano/transfer-money` | documentation_completeness | 8.0 |
| `rasano/transfer-money` | error_handling_quality | 8.0 |
| `rasano/transfer-money` | example_quality | 5.0 |
| `rasano/transfer-money` | instruction_clarity | 9.0 |
| `rasano/transfer-money` | professional_tone | 9.0 |
| `rasano/transfer-money` | scope_definition | 8.0 |
| `rasano/transfer-money` | trigger_simulation | 8.0 |
| `rasano/transfer-money` | workflow_completeness | 9.0 |
| `rasano/transfer-money#improved` | description_clarity | 9.0 |
| `rasano/transfer-money#improved` | documentation_completeness | 8.0 |
| `rasano/transfer-money#improved` | error_handling_quality | 8.0 |
| `rasano/transfer-money#improved` | example_quality | 5.0 |
| `rasano/transfer-money#improved` | instruction_clarity | 9.0 |
| `rasano/transfer-money#improved` | professional_tone | 9.0 |
| `rasano/transfer-money#improved` | scope_definition | 8.0 |
| `rasano/transfer-money#improved` | trigger_simulation | 8.0 |
| `rasano/transfer-money#improved` | workflow_completeness | 9.0 |
| `personalization/default-session-start` | description_clarity | 8.0 |
| `personalization/default-session-start` | documentation_completeness | 8.0 |
| `personalization/default-session-start` | error_handling_quality | 3.0 |
| `personalization/default-session-start` | example_quality | 4.0 |
| `personalization/default-session-start` | instruction_clarity | 8.0 |
| `personalization/default-session-start` | professional_tone | 9.0 |
| `personalization/default-session-start` | scope_definition | 8.0 |
| `personalization/default-session-start` | trigger_simulation | 5.0 |
| `personalization/default-session-start` | workflow_completeness | 7.0 |
| `personalization/default-session-start#improved` | description_clarity | 8.0 |
| `personalization/default-session-start#improved` | documentation_completeness | 7.0 |
| `personalization/default-session-start#improved` | error_handling_quality | 3.0 |
| `personalization/default-session-start#improved` | example_quality | 4.0 |
| `personalization/default-session-start#improved` | instruction_clarity | 8.0 |
| `personalization/default-session-start#improved` | professional_tone | 9.0 |
| `personalization/default-session-start#improved` | scope_definition | 8.0 |
| `personalization/default-session-start#improved` | trigger_simulation | 5.0 |
| `personalization/default-session-start#improved` | workflow_completeness | 7.0 |
| `personalization/view-transactions` | description_clarity | 8.0 |
| `personalization/view-transactions` | documentation_completeness | 7.0 |
| `personalization/view-transactions` | error_handling_quality | 5.0 |
| `personalization/view-transactions` | example_quality | 4.0 |
| `personalization/view-transactions` | instruction_clarity | 8.0 |
| `personalization/view-transactions` | professional_tone | 9.0 |
| `personalization/view-transactions` | scope_definition | 8.0 |
| `personalization/view-transactions` | trigger_simulation | 6.0 |
| `personalization/view-transactions` | workflow_completeness | 7.0 |
| `personalization/view-transactions#improved` | description_clarity | 9.0 |
| `personalization/view-transactions#improved` | documentation_completeness | 8.0 |
| `personalization/view-transactions#improved` | error_handling_quality | 6.0 |
| `personalization/view-transactions#improved` | example_quality | 5.0 |
| `personalization/view-transactions#improved` | instruction_clarity | 9.0 |
| `personalization/view-transactions#improved` | professional_tone | 9.0 |
| `personalization/view-transactions#improved` | scope_definition | 8.0 |
| `personalization/view-transactions#improved` | trigger_simulation | 8.0 |
| `personalization/view-transactions#improved` | workflow_completeness | 9.0 |

## What we ran

- Engine pin: mantle / rasa-pro 3.20.0.dev6
- Skills inventoried: 13
- SkillEvaluator CLI: yes
- Provider key: yes
- Improver rewrites: 13
- Actor models configured: lfm-1.2b, lfm-2.6b, llama-8b, nemotron-8b, muse-30b, gemma4-31b
- Actor models with live TSR: gemma4-31b, lfm-1.2b, lfm-2.6b, llama-8b, muse-30b, nemotron-8b

## Scope mix

- `engine-managed`: 2
- `project-global`: 7
- `skill-local`: 11

## Mantle-only inventory

- Skills with `requires_confirmation` on at least one tool: 5
- Extra frontmatter keys that Agent Skills schema rejects:
  - `tool_constraints`: 7 skills
  - `import_tools`: 6 skills
  - `routing`: 2 skills
  - `utter`: 1 skills

### High Mantle-native findings, 1

- `block_card` `confirmation.missing`, mantle_only. Irreversible tool order_replacement_card has no requires_confirmation.

## Mantle / Rasa issues this run

### 1. `rasa.train_failed` at `rasano/lfm-1.2b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 2. `rasa.train_failed` at `rasano/lfm-1.2b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 3. `rasa.train_failed` at `rasano/lfm-1.2b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 4. `rasa.train_failed` at `personalization/lfm-1.2b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 5. `rasa.train_failed` at `personalization/lfm-1.2b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 6. `rasa.train_failed` at `personalization/lfm-1.2b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 7. `rasa.train_failed` at `rasano/lfm-2.6b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 8. `rasa.train_failed` at `rasano/lfm-2.6b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 9. `rasa.train_failed` at `rasano/lfm-2.6b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 10. `rasa.train_failed` at `personalization/lfm-2.6b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 11. `rasa.train_failed` at `personalization/lfm-2.6b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 12. `rasa.train_failed` at `personalization/lfm-2.6b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 13. `rasa.train_failed` at `rasano/llama-8b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 14. `rasa.train_failed` at `rasano/llama-8b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 15. `rasa.train_failed` at `rasano/llama-8b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 16. `rasa.train_failed` at `personalization/llama-8b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 17. `rasa.train_failed` at `personalization/llama-8b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 18. `rasa.train_failed` at `personalization/llama-8b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 19. `rasa.train_failed` at `rasano/nemotron-8b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 20. `rasa.train_failed` at `rasano/nemotron-8b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 21. `rasa.train_failed` at `rasano/nemotron-8b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 22. `rasa.train_failed` at `personalization/nemotron-8b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 23. `rasa.train_failed` at `personalization/nemotron-8b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 24. `rasa.train_failed` at `personalization/nemotron-8b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 25. `rasa.train_failed` at `rasano/muse-30b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 26. `rasa.train_failed` at `rasano/muse-30b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 27. `rasa.train_failed` at `rasano/muse-30b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 28. `rasa.train_failed` at `personalization/muse-30b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 29. `rasa.train_failed` at `personalization/muse-30b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 30. `rasa.train_failed` at `personalization/muse-30b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 31. `rasa.train_failed` at `rasano/gemma4-31b/improved`

{"event_info": "Skill 'transfer_money' declares llm_settable field 'timing' with no run_after_setting_timing hook \u2014 direct writes only.", "skill_id": "transfer_money", "entry_name": "timing", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 32. `rasa.train_failed` at `rasano/gemma4-31b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 33. `rasa.train_failed` at `rasano/gemma4-31b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'load_profile'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 34. `rasa.train_failed` at `personalization/gemma4-31b/improved`

{"event_info": "Skill 'view_transactions' declares llm_settable field 'selected_account_id' with no run_after_setting_selected_account_id hook \u2014 direct writes only.", "skill_id": "view_transactions", "entry_name": "selected_account_id", "event": "mantle.validation.settable_field.no_post_write_hook", "level": "info"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 35. `rasa.train_failed` at `personalization/gemma4-31b/improved`

{"event_info": "Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "docs_url": null, "event": "mantle.validation.skill.failed_to_load", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

### 36. `rasa.train_failed` at `personalization/gemma4-31b/improved`

{"event_info": "Project validation found 1 problem(s):\n  - [mantle.validation.skill.failed_to_load] Skill directory 'skills/default_session_start' failed to load and would be silently skipped: Unknown step property 'done_when' on step 'identify'. Remove it or check for typos.. Fix the skill so it parses, or remove it.", "finding_count": 1, "event": "mantle.validate_project.project_validation_error", "level": "error"}

**Report this to Rasa.** rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

## Asks for Rasa

- Accept `SKILL.md` as an alias of `skill.md`.
- Kebab-case `name` matching the folder. Add `title:` for display names.
- Stamp `license` and `metadata.author` on official examples.
- Leave Mantle-only keys on the skill, or put them in `config/mantle.yml`.
- rasa train failed on a copied Mantle agent tree. Quote the engine message in this run's Mantle / Rasa issues section when filing.

