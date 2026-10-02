"""Ping an OpenAI-compatible local llama-server with a one-token chat call."""

from __future__ import annotations

import argparse
import sys

import httpx
from loguru import logger


def smoke_chat(base_url: str, model: str, timeout_sec: float) -> str:
    """POST a tiny chat completion and return the assistant text."""
    url = base_url.rstrip("/") + "/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word ok."}],
        "max_tokens": 8,
        "temperature": 0,
        "stream": False,
    }
    response = httpx.post(url, json=payload, timeout=timeout_sec)
    response.raise_for_status()
    body = response.json()
    choices = body.get("choices") or []
    if not choices:
        raise RuntimeError(f"empty choices from {url}: {body}")
    message = choices[0].get("message") or {}
    text = str(message.get("content") or message.get("reasoning_content") or "").strip()
    if not text:
        raise RuntimeError(f"empty message from {url}: {body}")
    return text


def main() -> None:
    """CLI: --base-url and --model, print the reply or exit 1."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base, e.g. http://127.0.0.1:8081/v1")
    parser.add_argument("--model", required=True, help="Model alias advertised by llama-server")
    parser.add_argument("--timeout-sec", type=float, default=120.0)
    args = parser.parse_args()
    try:
        text = smoke_chat(args.base_url, args.model, args.timeout_sec)
    except Exception as exc:  # noqa: BLE001
        logger.error("smoke failed: {}", exc)
        sys.exit(1)
    logger.info("smoke ok model={} reply={}", args.model, text[:80])


if __name__ == "__main__":
    main()
