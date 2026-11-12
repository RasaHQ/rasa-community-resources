"""Rubric, Tier 2, and optional Tier 3 on projected Agent Skills copies."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval.config import LlmEndpointSettings, NvidiaSettings
from rasa_skill_eval.models import NvidiaSkillResult
from rasa_skill_eval.nvidia_runner import (
    _run,
    judge_unavailable,
    parse_rubric,
    parse_similarity_pairs,
    parse_skill_lift,
    resolve_skillevaluator,
    skill_evaluator_env,
    stage_collection_for_evaluator,
    stage_skill_for_evaluator,
)


def nvidia_key_configured() -> bool:
    """Return True when NVIDIA_API_KEY, OPENAI_API_KEY, or ANTHROPIC_API_KEY is set."""
    load_dotenv()
    return bool(
        os.getenv("NVIDIA_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
    )


def _json_extract_failed(stdout: str, stderr: str) -> bool:
    """True when SkillEvaluator fell back because the judge did not return JSON."""
    blob = f"{stdout}\n{stderr}".lower()
    return "could not extract valid json" in blob


def _clear_json_reports(output_dir: Path) -> None:
    """Remove leftover SkillEvaluator JSON so a retry is not poisoned."""
    if not output_dir.is_dir():
        return
    for path in output_dir.glob("**/*.json"):
        path.unlink()


def _backup_skill_eval_env(
    settings: NvidiaSettings,
    judge: LlmEndpointSettings | None,
) -> dict[str, str] | None:
    """SkillEvaluator env for ``llm.judge`` backup, or None when unconfigured."""
    if judge is None or not judge.backup_model:
        return None
    provider = judge.backup_provider or judge.provider
    return skill_evaluator_env(
        settings,
        llm_model=judge.backup_model,
        llm_provider=provider,
    )


def _rubric_skip_reason(stdout: str, stderr: str, unavailable: bool) -> str:
    """Prefer JSON-extract failure over an EOL label when the LLM did reply."""
    if _json_extract_failed(stdout, stderr):
        return "rubric-eval produced no parseable score"
    if unavailable:
        return "SkillEvaluator rubric LLM unavailable (EOL or missing model)"
    return "rubric-eval produced no score"


def rubric_eval_skill(
    projected_dir: Path,
    output_dir: Path,
    settings: NvidiaSettings,
    skill_id: str | None = None,
    judge: LlmEndpointSettings | None = None,
) -> NvidiaSkillResult:
    """Run ``skillevaluator rubric-eval`` when a provider key exists."""
    prefix = resolve_skillevaluator()
    label = skill_id or projected_dir.name
    if prefix is None:
        return NvidiaSkillResult(
            skill_id=label,
            command="rubric-eval",
            skipped=True,
            skip_reason="skillevaluator CLI not found",
        )
    if not nvidia_key_configured():
        return NvidiaSkillResult(
            skill_id=label,
            command="rubric-eval",
            skipped=True,
            skip_reason="no NVIDIA_API_KEY / OPENAI_API_KEY / ANTHROPIC_API_KEY",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    prior_score, prior_criteria = parse_rubric(output_dir)
    if prior_score is not None:
        return NvidiaSkillResult(
            skill_id=label,
            command="rubric-eval",
            skipped=False,
            report_files=[str(p) for p in output_dir.glob("*")],
            rubric_score=prior_score,
            rubric_criteria=prior_criteria,
            quality_score=prior_score,
        )

    def _invoke(extra_env: dict[str, str]) -> subprocess.CompletedProcess[str] | NvidiaSkillResult:
        """Run one rubric-eval CLI invocation with the given SkillEvaluator env."""
        try:
            with stage_skill_for_evaluator(projected_dir) as (staged, staging_root):
                return _run(
                    prefix,
                    [
                        "rubric-eval",
                        str(staged),
                        "--min-score",
                        str(settings.min_score),
                        "-r",
                        "json",
                        "-o",
                        str(output_dir),
                    ],
                    cwd=staging_root,
                    timeout=settings.validate_timeout_sec,
                    extra_env=extra_env,
                )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            return NvidiaSkillResult(
                skill_id=label,
                command="rubric-eval",
                skipped=True,
                skip_reason=str(exc),
            )

    proc = _invoke(skill_evaluator_env(settings))
    if isinstance(proc, NvidiaSkillResult):
        return proc
    score, criteria = parse_rubric(output_dir)
    stdout = proc.stdout
    stderr = proc.stderr
    if score is None:
        backup_env = _backup_skill_eval_env(settings, judge)
        should_retry = backup_env is not None and (
            _json_extract_failed(stdout, stderr)
            or judge_unavailable(output_dir, stdout, stderr)
        )
        if should_retry and backup_env is not None:
            logger.info("Retrying rubric-eval for {} with backup judge env", label)
            _clear_json_reports(output_dir)
            retry = _invoke(backup_env)
            if isinstance(retry, NvidiaSkillResult):
                return retry
            proc = retry
            stdout = proc.stdout
            stderr = proc.stderr
            score, criteria = parse_rubric(output_dir)
    unavailable = judge_unavailable(output_dir, stdout, stderr)
    if score is not None:
        return NvidiaSkillResult(
            skill_id=label,
            command="rubric-eval",
            exit_code=proc.returncode,
            skipped=False,
            stdout=stdout[-8000:],
            stderr=stderr[-8000:],
            report_files=[str(p) for p in output_dir.glob("*")],
            rubric_score=score,
            rubric_criteria=criteria,
            quality_score=score,
        )
    return NvidiaSkillResult(
        skill_id=label,
        command="rubric-eval",
        exit_code=proc.returncode,
        skipped=True,
        skip_reason=_rubric_skip_reason(stdout, stderr, unavailable),
        stdout=stdout[-8000:],
        stderr=stderr[-8000:],
        report_files=[str(p) for p in output_dir.glob("*")],
        rubric_score=None,
        rubric_criteria=criteria,
    )


def similarity_check_collection(
    collection_dir: Path,
    output_dir: Path,
    settings: NvidiaSettings,
) -> NvidiaSkillResult:
    """Run Tier 2 ``similarity-check`` across a folder of projected skills."""
    prefix = resolve_skillevaluator()
    if prefix is None:
        return NvidiaSkillResult(
            skill_id=collection_dir.name,
            command="similarity-check",
            skipped=True,
            skip_reason="skillevaluator CLI not found",
        )
    if not nvidia_key_configured():
        return NvidiaSkillResult(
            skill_id=collection_dir.name,
            command="similarity-check",
            skipped=True,
            skip_reason="no embeddings provider key",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    prior_pairs = parse_similarity_pairs(output_dir)
    if prior_pairs is not None:
        return NvidiaSkillResult(
            skill_id=collection_dir.name,
            command="similarity-check",
            skipped=False,
            report_files=[str(p) for p in output_dir.glob("*")],
            similarity_pairs=prior_pairs,
        )
    extra_env = skill_evaluator_env(settings)
    try:
        with stage_collection_for_evaluator(collection_dir) as (skills_root, staging_root):
            proc = _run(
                prefix,
                [
                    "similarity-check",
                    str(skills_root),
                    "--type",
                    "skill",
                    "--model",
                    settings.embedding_model,
                    "-r",
                    "json",
                    "-o",
                    str(output_dir),
                ],
                cwd=staging_root,
                timeout=settings.validate_timeout_sec * 2,
                extra_env=extra_env,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return NvidiaSkillResult(
            skill_id=collection_dir.name,
            command="similarity-check",
            skipped=True,
            skip_reason=str(exc),
        )
    pairs = parse_similarity_pairs(output_dir)
    unavailable = judge_unavailable(output_dir, proc.stdout, proc.stderr)
    if pairs is not None:
        return NvidiaSkillResult(
            skill_id=collection_dir.name,
            command="similarity-check",
            exit_code=proc.returncode,
            skipped=False,
            stdout=proc.stdout[-8000:],
            stderr=proc.stderr[-8000:],
            report_files=[str(p) for p in output_dir.glob("*")],
            similarity_pairs=pairs,
        )
    reason = "similarity-check failed"
    if unavailable:
        reason = "SkillEvaluator embedding model unavailable (EOL or missing model)"
    else:
        reason = "similarity-check produced no usable pair count"
    return NvidiaSkillResult(
        skill_id=collection_dir.name,
        command="similarity-check",
        exit_code=proc.returncode,
        skipped=True,
        skip_reason=reason,
        stdout=proc.stdout[-8000:],
        stderr=proc.stderr[-8000:],
        report_files=[str(p) for p in output_dir.glob("*")],
        similarity_pairs=None,
    )


_DOCTOR_CACHE: tuple[bool, str] | None = None


def tier3_doctor(settings: NvidiaSettings) -> tuple[bool, str]:
    """Return (ok, reason) after ``skillevaluator tier3 doctor``."""
    global _DOCTOR_CACHE
    if _DOCTOR_CACHE is not None:
        return _DOCTOR_CACHE
    prefix = resolve_skillevaluator()
    if prefix is None:
        _DOCTOR_CACHE = (False, "skillevaluator CLI not found")
        return _DOCTOR_CACHE
    if not nvidia_key_configured():
        _DOCTOR_CACHE = (False, "no provider key for Tier 3 grading")
        return _DOCTOR_CACHE
    try:
        proc = _run(
            prefix,
            [
                "tier3",
                "doctor",
                "--env-mode",
                settings.tier3_env_mode,
                "--agents",
                settings.tier3_agents,
            ],
            cwd=Path.cwd(),
            timeout=120,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        _DOCTOR_CACHE = (False, str(exc))
        return _DOCTOR_CACHE
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout)[-400:]
        _DOCTOR_CACHE = (False, tail or f"tier3 doctor exit {proc.returncode}")
        return _DOCTOR_CACHE
    _DOCTOR_CACHE = (True, "ok")
    return _DOCTOR_CACHE


def tier3_evaluate_skill(
    projected_dir: Path,
    output_dir: Path,
    settings: NvidiaSettings,
    skill_id: str | None = None,
) -> NvidiaSkillResult:
    """Run Harbor live eval on one projected skill. Skip-clean when doctor fails."""
    label = skill_id or projected_dir.name
    prefix = resolve_skillevaluator()
    if prefix is None:
        return NvidiaSkillResult(
            skill_id=label,
            command="tier3-evaluate",
            skipped=True,
            skip_reason="skillevaluator CLI not found",
        )
    ok, reason = tier3_doctor(settings)
    if not ok:
        return NvidiaSkillResult(
            skill_id=label,
            command="tier3-evaluate",
            skipped=True,
            skip_reason=f"tier3 doctor: {reason}",
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    try:
        with stage_skill_for_evaluator(projected_dir) as (staged, staging_root):
            proc = _run(
                prefix,
                [
                    "tier3",
                    "evaluate",
                    str(staged),
                    "--agents",
                    settings.tier3_agents,
                    "--env-mode",
                    settings.tier3_env_mode,
                    "-r",
                    "json",
                    "-o",
                    str(output_dir),
                ],
                cwd=staging_root,
                timeout=settings.tier3_timeout_sec,
            )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        return NvidiaSkillResult(
            skill_id=label,
            command="tier3-evaluate",
            skipped=True,
            skip_reason=str(exc),
        )
    lift, pass_k = parse_skill_lift(output_dir)
    return NvidiaSkillResult(
        skill_id=label,
        command="tier3-evaluate",
        exit_code=proc.returncode,
        stdout=proc.stdout[-8000:],
        stderr=proc.stderr[-8000:],
        report_files=[str(p) for p in output_dir.glob("*")],
        skill_lift=lift,
        pass_at_k=pass_k,
    )
