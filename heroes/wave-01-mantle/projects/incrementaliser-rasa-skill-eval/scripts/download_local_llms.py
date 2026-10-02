"""Download Q4_K_M GGUF weights for local Layer B actor models."""

from __future__ import annotations

import argparse

from dotenv import load_dotenv

from rasa_skill_eval import PROJECT_ROOT
from rasa_skill_eval.local_llm import GGUF_SPECS, MODELS_DIR, download_gguf

LFM_IDS = ("lfm-1.2b", "lfm-2.6b")
EIGHT_B_IDS = ("llama-8b", "nemotron-8b")
THIRTY_B_IDS = ("muse-30b", "gemma4-31b")


def _parse_ids(tier: str) -> tuple[str, ...]:
    """Map a CLI tier name to catalog ids."""
    if tier == "lfm":
        return LFM_IDS
    if tier == "8b":
        return EIGHT_B_IDS
    if tier == "30b":
        return THIRTY_B_IDS
    if tier == "all":
        return tuple(GGUF_SPECS)
    raise ValueError(f"Unknown tier: {tier}")


def main() -> None:
    """Download selected local GGUF weights into ``models/``."""
    load_dotenv(PROJECT_ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tier",
        choices=("lfm", "8b", "30b", "all"),
        default="all",
        help="lfm = 1.2B+2.6B, 8b = llama+nemotron, 30b = muse+gemma, all = catalog",
    )
    args = parser.parse_args()
    for model_id in _parse_ids(args.tier):
        download_gguf(model_id, MODELS_DIR)


if __name__ == "__main__":
    main()
