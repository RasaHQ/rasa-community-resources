"""Shim. Prefer ``uv run eval-all``."""

from rasa_skill_eval.cli import eval_all_main

if __name__ == "__main__":
    eval_all_main()
