# Fetched corpora

Clones are gitignored. Run `uv run fetch-corpus` to populate:

- `rasano/`. Mantle voice banking from community-resources.
- `personalization/`. Session-start personalization pattern.
- `writing-for-agents/`. Matt Pocock improver skill (prompt only; not NVIDIA-scored).
- `evaluation-harness/`. Community evaluation pattern reference.

Commit SHAs are written to `pins/*.sha`. Do not edit cloned trees. Re-fetch instead.
