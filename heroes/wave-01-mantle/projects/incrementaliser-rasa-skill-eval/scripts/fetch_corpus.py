"""Shim. Prefer ``uv run fetch-corpus``."""

from rasa_skill_eval.cli import fetch_corpus_main

if __name__ == "__main__":
    fetch_corpus_main()
