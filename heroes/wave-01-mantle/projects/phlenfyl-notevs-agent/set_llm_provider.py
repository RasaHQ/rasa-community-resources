#!/usr/bin/env python3
"""Rewrites integrations.yml's llm: block to match LLM_PROVIDER (default: groq).

Mirrors the NoteVs VS Code extension's writeLlmConfig() in agentProcess.ts —
same three providers, same models, same api_key_env names — so this repo and
the extension never disagree on what "provider X" means. Run by start.sh
before every `rasa run`.
"""
import os
import re
import sys

LLM_PROVIDERS = {
    "groq": {
        "api_key_env": "GROQ_API_KEY",
        "model": "qwen/qwen3.8-27b",
        "extra": "  reasoning_effort: none\n",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "model": "gpt-4o-mini",
        "extra": "",
    },
    "anthropic": {
        "api_key_env": "ANTHROPIC_API_KEY",
        "model": "claude-3-5-haiku-20241022",
        "extra": "",
    },
}


def main() -> None:
    provider = os.environ.get("LLM_PROVIDER", "groq")
    if provider not in LLM_PROVIDERS:
        print(
            f"Unknown LLM_PROVIDER '{provider}' — must be one of {', '.join(LLM_PROVIDERS)}",
            file=sys.stderr,
        )
        sys.exit(1)

    info = LLM_PROVIDERS[provider]
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "integrations.yml")
    with open(path, "r") as f:
        content = f.read()

    new_block = (
        f"llm:\n"
        f"  provider: {provider}\n"
        f"  model: {info['model']}\n"
        f"  api_key_env: {info['api_key_env']}\n"
        f"{info['extra']}"
    )
    # Matches from the `llm:` line up to (not including) the next
    # non-indented line — the whole block, comments and all, regardless of
    # exactly which fields the file currently has under it.
    updated = re.sub(r"^llm:\n(?:[ \t].*\n?)*", new_block, content, count=1, flags=re.MULTILINE)
    with open(path, "w") as f:
        f.write(updated)

    print(f"integrations.yml llm: block set to provider={provider}, model={info['model']}")


if __name__ == "__main__":
    main()
