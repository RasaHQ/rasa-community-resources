"""Evaluate Rasa Mantle skills with NVIDIA SkillEvaluator and Mantle-native checks."""

from __future__ import annotations

__all__ = ["PROJECT_ROOT"]

from pathlib import Path

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
