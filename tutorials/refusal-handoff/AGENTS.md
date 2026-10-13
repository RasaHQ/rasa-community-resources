# Refusal handoff experiment

Both variants must differ only by the `@skill.` prefix in the blocked-request
skill. Keep the tool results, agent, model, messages and other instructions the
same. The detour tools are harmless observation points, not alternate ways to
perform the task.

Preserve three proof types separately: native compilation/classification;
replay-predicate controls using synthetic events; actual model-driven episodes.
Do not relabel the first two as model behaviour. Retain failed traces and do
not rerun paid episodes merely to reread saved data. Publish no rate, ranking or
cost comparison here. Private benchmark studies belong in the benchmark repo.

Use one environment for both variants. Prepare source only; never copy
`.venv`, credentials, caches or trained models from another experiment. New
run directories are required when source changes. Model and speech keys are
not needed for the offline controls; this example is text-only.
