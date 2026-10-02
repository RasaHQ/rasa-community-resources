"""Run NVIDIA SkillEvaluator against projected skill directories."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval.config import NvidiaSettings
from rasa_skill_eval.models import NvidiaSkillResult

SKILL_EVALUATOR_SPEC = "skillevaluator[all] @ git+https://github.com/NVIDIA/SkillEvaluator.git"


def resolve_skillevaluator() -> list[str] | None:
    """Return the argv prefix for SkillEvaluator, or None if missing."""
    direct = shutil.which("skillevaluator")
    if direct:
        return [direct]
    for name in ("skillevaluator.exe", "skillevaluator"):
        candidate = Path.home() / ".local" / "bin" / name
        if candidate.is_file():
            return [str(candidate)]
    uv = shutil.which("uv")
    if uv:
        return [uv, "tool", "run", "--from", SKILL_EVALUATOR_SPEC, "skillevaluator"]
    uvx = shutil.which("uvx")
    if uvx:
        return [uvx, "--from", SKILL_EVALUATOR_SPEC, "skillevaluator"]
    return None


@contextmanager
def stage_skill_for_evaluator(projected_dir: Path) -> Iterator[tuple[Path, Path]]:
    """Copy one skill under ``skills/<name>/`` without sidecars for SkillEvaluator.

    Yields ``(staged_skill_dir, staging_root)``. CLI ``cwd`` should be ``staging_root``.
    """
    projected_dir = projected_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="skilleval-") as tmp:
        root = Path(tmp)
        staged = root / "skills" / projected_dir.name
        shutil.copytree(
            projected_dir,
            staged,
            ignore=shutil.ignore_patterns("projection.json", ".sidecars"),
        )
        yield staged, root


@contextmanager
def stage_collection_for_evaluator(collection_dir: Path) -> Iterator[tuple[Path, Path]]:
    """Copy every SKILL.md folder under ``skills/`` for a collection-level CLI."""
    collection_dir = collection_dir.resolve()
    with tempfile.TemporaryDirectory(prefix="skilleval-col-") as tmp:
        root = Path(tmp)
        skills_root = root / "skills"
        skills_root.mkdir(parents=True, exist_ok=True)
        for child in sorted(collection_dir.iterdir()):
            if not child.is_dir() or child.name.startswith("."):
                continue
            if not (child / "SKILL.md").is_file():
                continue
            shutil.copytree(
                child,
                skills_root / child.name,
                ignore=shutil.ignore_patterns("projection.json", ".sidecars"),
            )
        yield skills_root, root


def parse_schema_high(report_dir: Path) -> list[str]:
    """Return SCHEMA HIGH messages from SkillEvaluator JSON under ``report_dir``."""
    found: list[str] = []
    for data in _iter_json(report_dir):
        found.extend(_schema_high_from_obj(data))
    # Preserve order, drop duplicates.
    seen: set[str] = set()
    out: list[str] = []
    for message in found:
        if message in seen:
            continue
        seen.add(message)
        out.append(message)
    return out


def _schema_high_from_obj(data: Any) -> list[str]:
    """Walk SkillEvaluator JSON for high-severity SCHEMA findings."""
    found: list[str] = []
    if isinstance(data, dict):
        severity = str(data.get("severity") or "").lower()
        category = str(data.get("category") or "")
        check = str(data.get("check_name") or "")
        schema_hit = category.upper() == "SCHEMA" or "schema" in check.lower()
        if severity == "high" and schema_hit:
            message = str(data.get("message") or "").strip()
            if message:
                found.append(message)
        for value in data.values():
            found.extend(_schema_high_from_obj(value))
    elif isinstance(data, list):
        for item in data:
            found.extend(_schema_high_from_obj(item))
    return found


def unique_json_file_count(directory: Path) -> int:
    """Count unique JSON files under ``directory`` without double-counting globs."""
    seen: set[Path] = set()
    for path in list(directory.glob("*.json")) + list(directory.glob("**/*.json")):
        seen.add(path.resolve())
    return len(seen)


def parse_similarity_pairs(report_dir: Path) -> int | None:
    """Return the number of similarity matches, or None when the report is unusable."""
    payloads = _iter_json(report_dir)
    if not payloads:
        return None
    pairs = 0
    found_report = False
    for data in payloads:
        count, present = _similarity_pair_count(data)
        if present:
            found_report = True
            pairs += count
    if found_report:
        return pairs
    if any(_judge_unavailable_in_obj(data) for data in payloads):
        return None
    if any(_command_failed_without_pairs(data) for data in payloads):
        return None
    return 0


def nvidia_command_successful(item: NvidiaSkillResult) -> bool:
    """True when a SkillEvaluator command produced the result it is supposed to."""
    if item.skipped:
        return False
    if item.command == "quality-check":
        return item.quality_score is not None
    if item.command == "rubric-eval":
        return item.rubric_score is not None
    if item.command == "similarity-check":
        return item.similarity_pairs is not None
    if item.command == "validate":
        return True
    return item.exit_code == 0


def judge_unavailable(report_dir: Path, stdout: str = "", stderr: str = "") -> bool:
    """True when SkillEvaluator recorded an EOL or missing LLM/embedding judge."""
    blob = f"{stdout}\n{stderr}".lower()
    if "llm_unavailable" in blob or "end of life" in blob:
        return True
    return any(_judge_unavailable_in_obj(data) for data in _iter_json(report_dir))


def _judge_unavailable_in_obj(data: Any) -> bool:
    """Walk SkillEvaluator JSON for llm_unavailable or EOL embedding errors."""
    if isinstance(data, dict):
        check = str(data.get("check_name") or "").lower()
        if check == "llm_unavailable":
            return True
        message = str(data.get("message") or data.get("detail") or "").lower()
        if "end of life" in message or "llm judge unavailable" in message:
            return True
        errors = data.get("errors")
        if isinstance(errors, list) and any(
            "end of life" in str(item).lower() for item in errors
        ):
            return True
        legacy = data.get("legacy")
        if isinstance(legacy, dict):
            if _judge_unavailable_in_obj(legacy):
                return True
        for value in data.values():
            if _judge_unavailable_in_obj(value):
                return True
    elif isinstance(data, list):
        return any(_judge_unavailable_in_obj(item) for item in data)
    return False


def _command_failed_without_pairs(data: Any) -> bool:
    """True when a similarity report failed before producing match findings."""
    if not isinstance(data, dict):
        return False
    _count, present = _similarity_pair_count(data)
    if present:
        return False
    status = str(data.get("overall_status") or data.get("status") or "").lower()
    passed = data.get("overall_passed")
    if passed is False or status == "failed":
        errors = 0
        if isinstance(data.get("total_errors"), int):
            errors = int(data["total_errors"])
        summary = data.get("summary")
        if isinstance(summary, dict) and isinstance(summary.get("errors"), int):
            errors = max(errors, int(summary["errors"]))
        if errors > 0 or _judge_unavailable_in_obj(data):
            return True
    return False


def _similarity_pair_count(data: Any) -> tuple[int, bool]:
    """Return (pair count, whether this object is a similarity report)."""
    if isinstance(data, list):
        total = 0
        present = False
        for item in data:
            count, hit = _similarity_pair_count(item)
            total += count
            present = present or hit
        return total, present
    if not isinstance(data, dict):
        return 0, False
    findings = data.get("findings")
    if isinstance(findings, list):
        pairs = [
            item
            for item in findings
            if isinstance(item, dict)
            and (
                str(item.get("category") or "").upper() == "SIMILARITY"
                or (
                    isinstance(item.get("metadata"), dict)
                    and item["metadata"].get("entry_a")
                    and item["metadata"].get("entry_b")
                )
            )
        ]
        if pairs:
            return len(pairs), True
    for key in ("similarity_pairs", "pair_count", "duplicate_count"):
        raw = data.get(key)
        if isinstance(raw, int):
            return raw, True
        if isinstance(raw, list):
            return len(raw), True
    present = False
    total = 0
    for key in ("results", "success_details"):
        nested = data.get(key)
        if nested is None:
            continue
        count, hit = _similarity_pair_count(nested)
        total += count
        present = present or hit
    return total, present


def _iter_json(report_dir: Path) -> list[Any]:
    """Load every JSON document under ``report_dir``."""
    payloads: list[Any] = []
    seen: set[Path] = set()
    candidates = list(report_dir.glob("*.json")) + list(report_dir.glob("**/*.json"))
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        try:
            payloads.append(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    return payloads


def _parse_quality(report_dir: Path) -> tuple[float | None, str | None]:
    """Extract composite score and grade from SkillEvaluator JSON."""
    for data in _iter_json(report_dir):
        score, grade = _score_from_obj(data)
        if score is not None:
            return score, grade
    return None, None


def parse_quality_dimensions(report_dir: Path) -> dict[str, float]:
    """Return correctness/discoverability/reliability/efficiency scores when present."""
    for data in _iter_json(report_dir):
        dims = _dimensions_from_obj(data)
        if dims:
            return dims
    return {}


def _dimensions_from_obj(data: Any) -> dict[str, float]:
    """Walk SkillEvaluator JSON for a dimensions map with numeric scores."""
    found: dict[str, float] = {}
    if isinstance(data, dict):
        quality = data.get("quality")
        if isinstance(quality, dict):
            raw = quality.get("dimensions") or quality.get("category_scores")
            found.update(_normalize_dimension_map(raw))
        raw_top = data.get("dimensions")
        found.update(_normalize_dimension_map(raw_top))
        for key in ("results", "quality_summary", "success_details"):
            nested = data.get(key)
            if isinstance(nested, list):
                for item in nested:
                    found.update(_dimensions_from_obj(item))
                    if isinstance(item, dict):
                        found.update(_dimensions_from_obj(item.get("metadata")))
    if isinstance(data, list):
        for item in data:
            found.update(_dimensions_from_obj(item))
    return found


def _normalize_dimension_map(raw: Any) -> dict[str, float]:
    """Accept {name: score} or {name: {score: n}}."""
    out: dict[str, float] = {}
    if not isinstance(raw, dict):
        return out
    for name, value in raw.items():
        if isinstance(value, (int, float)):
            out[str(name)] = float(value)
        elif isinstance(value, dict):
            score = value.get("score") or value.get("overall_score")
            if isinstance(score, (int, float)):
                out[str(name)] = float(score)
    return out


def parse_rubric(report_dir: Path) -> tuple[float | None, dict[str, float]]:
    """Extract rubric overall score and per-criterion scores."""
    best_criteria: dict[str, float] = {}
    for data in _iter_json(report_dir):
        score, criteria = _rubric_from_obj(data)
        if score is not None:
            return score, criteria or best_criteria
        if criteria:
            best_criteria.update(criteria)
    if best_criteria:
        return _overall_from_criteria(best_criteria), best_criteria
    return None, {}


def _overall_from_criteria(criteria: dict[str, float]) -> float:
    """Derive a 0–100 overall when SkillEvaluator omitted ``overall_score``."""
    mean = sum(criteria.values()) / len(criteria)
    if all(value <= 10.0 for value in criteria.values()):
        return round(mean * 10.0, 1)
    return float(mean)


def _numeric_score(value: Any) -> float | None:
    """Return a float score, ignoring bools which subclass int."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _criteria_from_checks(raw_crit: Any) -> dict[str, float]:
    """Parse rubric checks, criteria lists, or name→score maps."""
    criteria: dict[str, float] = {}
    if isinstance(raw_crit, list):
        for item in raw_crit:
            if not isinstance(item, dict):
                continue
            name = str(
                item.get("id") or item.get("name") or item.get("criterion") or ""
            ).strip()
            raw = item.get("score")
            if raw is None:
                raw = item.get("overall_score")
            cscore = _numeric_score(raw)
            if name and cscore is not None:
                criteria[name] = cscore
    elif isinstance(raw_crit, dict):
        criteria.update(_normalize_dimension_map(raw_crit))
    return criteria


def _criteria_from_findings(findings: list[Any]) -> dict[str, float]:
    """Parse per-criterion scores from SkillEvaluator rubric findings."""
    criteria: dict[str, float] = {}
    for item in findings:
        if not isinstance(item, dict):
            continue
        check = str(item.get("check_name") or "").lower()
        if check in {"llm_unavailable", "llm judge unavailable"}:
            continue
        meta = item.get("metadata")
        if not isinstance(meta, dict):
            continue
        name = str(meta.get("id") or item.get("check_name") or "").strip()
        cscore = _numeric_score(meta.get("score"))
        if name and cscore is not None:
            criteria[name] = cscore
    return criteria


def _rubric_from_obj(data: Any) -> tuple[float | None, dict[str, float]]:
    """Walk JSON for rubric overall + named criteria, including ``rubric_eval``."""
    score: float | None = None
    criteria: dict[str, float] = {}
    if isinstance(data, list):
        for item in data:
            nscore, ncrit = _rubric_from_obj(item)
            if nscore is not None:
                score = nscore
            criteria.update(ncrit)
        return score, criteria
    if not isinstance(data, dict):
        return None, {}
    nested_eval = data.get("rubric_eval")
    if isinstance(nested_eval, dict):
        nscore, ncrit = _rubric_from_obj(nested_eval)
        if nscore is not None:
            score = nscore
        criteria.update(ncrit)
    nested_rubric = data.get("rubric")
    if isinstance(nested_rubric, dict):
        nscore, ncrit = _rubric_from_obj(nested_rubric)
        if nscore is not None:
            score = nscore
        criteria.update(ncrit)
    looks_like_rubric = (
        "checks" in data
        or "criterion_scores" in data
        or "criteria" in data
        or "judge_score" in data
        or data.get("execution_status") is not None
    )
    if looks_like_rubric or "quality" not in data:
        raw_score = _numeric_score(data.get("overall_score"))
        if raw_score is None:
            raw_score = _numeric_score(data.get("weighted_score"))
        if raw_score is not None and "quality" not in data:
            score = raw_score
        criteria.update(
            _criteria_from_checks(
                data.get("checks") or data.get("criteria") or data.get("criterion_scores")
            )
        )
        findings = data.get("findings")
        if isinstance(findings, list):
            criteria.update(_criteria_from_findings(findings))
    for key in ("results", "success_details"):
        nested = data.get(key)
        if nested is None:
            continue
        nscore, ncrit = _rubric_from_obj(nested)
        if nscore is not None:
            score = nscore
        criteria.update(ncrit)
    return score, criteria


def parse_skill_lift(report_dir: Path) -> tuple[float | None, float | None]:
    """Extract Tier 3 Skill Lift and pass@k when present."""
    lift: float | None = None
    pass_k: float | None = None
    for data in _iter_json(report_dir):
        values = _walk_lift(data)
        if values[0] is not None:
            lift = values[0]
        if values[1] is not None:
            pass_k = values[1]
    return lift, pass_k


def _walk_lift(data: Any) -> tuple[float | None, float | None]:
    """Find skill_lift / pass_at_k keys in a JSON tree."""
    lift: float | None = None
    pass_k: float | None = None
    if isinstance(data, dict):
        for key, value in data.items():
            lowered = key.lower().replace("-", "_")
            if lowered in {"skill_lift", "lift"} and isinstance(value, (int, float)):
                lift = float(value)
            if lowered in {"pass_at_k", "pass@k", "pass_at_k_mean"} and isinstance(
                value, (int, float)
            ):
                pass_k = float(value)
            nested = _walk_lift(value)
            if nested[0] is not None:
                lift = nested[0]
            if nested[1] is not None:
                pass_k = nested[1]
    elif isinstance(data, list):
        for item in data:
            nested = _walk_lift(item)
            if nested[0] is not None:
                lift = nested[0]
            if nested[1] is not None:
                pass_k = nested[1]
    return lift, pass_k


def _grade_of(data: dict[str, Any]) -> str | None:
    """Return a letter grade from a quality object."""
    grade = data.get("grade") or data.get("quality_grade") or data.get("letter_grade")
    if grade is None or grade == "":
        return None
    return str(grade)


def _score_from_obj(data: Any) -> tuple[float | None, str | None]:
    """Prefer overall_score from SkillEvaluator JSON, not a per-dimension score."""
    if isinstance(data, dict):
        quality = data.get("quality")
        if isinstance(quality, dict) and isinstance(quality.get("overall_score"), (int, float)):
            return float(quality["overall_score"]), _grade_of(quality)
        summary = data.get("quality_summary")
        if isinstance(summary, list):
            for item in summary:
                score, grade = _score_from_obj(item)
                if score is not None:
                    return score, grade
        if isinstance(data.get("overall_score"), (int, float)):
            return float(data["overall_score"]), _grade_of(data)
        details = data.get("success_details")
        if isinstance(details, list):
            for item in details:
                if not isinstance(item, dict):
                    continue
                meta = item.get("metadata")
                if isinstance(meta, dict) and isinstance(meta.get("overall_score"), (int, float)):
                    return float(meta["overall_score"]), _grade_of(meta)
        results = data.get("results")
        if isinstance(results, list):
            for item in results:
                score, grade = _score_from_obj(item)
                if score is not None:
                    return score, grade
    if isinstance(data, list):
        for item in data:
            score, grade = _score_from_obj(item)
            if score is not None:
                return score, grade
    return None, None


def skill_evaluator_env(
    settings: NvidiaSettings,
    *,
    llm_model: str | None = None,
    llm_provider: str | None = None,
) -> dict[str, str]:
    """Pin live chat and embedding models for SkillEvaluator subprocesses."""
    provider = (llm_provider or "nv_build").strip().lower()
    if provider == "nvidia":
        provider = "nv_build"
    return {
        "SKILL_EVAL_LLM_PROVIDER": provider,
        "SKILL_EVAL_LLM_MODEL": llm_model or settings.rubric_model,
        "SKILL_EVAL_EMBEDDING_PROVIDER": "nv_build",
        "SKILL_EVAL_EMBEDDING_MODEL": settings.embedding_model,
    }


def _run(
    prefix: list[str],
    args: list[str],
    cwd: Path,
    timeout: int,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run SkillEvaluator and capture text output."""
    cmd = [*prefix, *args]
    logger.info("Running {}", " ".join(cmd))
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
        env=env,
    )


def evaluate_skill(
    projected_dir: Path,
    output_dir: Path,
    settings: NvidiaSettings,
    prefix: list[str] | None = None,
    skill_id: str | None = None,
) -> list[NvidiaSkillResult]:
    """Run keyless quality-check and scoped validate on a projected skill."""
    load_dotenv()
    projected_dir = projected_dir.resolve()
    output_dir = output_dir.resolve()
    label = skill_id or projected_dir.name
    resolved = prefix if prefix is not None else resolve_skillevaluator()
    output_dir.mkdir(parents=True, exist_ok=True)
    if resolved is None:
        skip = NvidiaSkillResult(
            skill_id=label,
            command="skillevaluator",
            skipped=True,
            skip_reason="skillevaluator CLI not found on PATH. Install via uv tool.",
        )
        return [skip]

    results: list[NvidiaSkillResult] = []
    quality_dir = output_dir / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    validate_dir = output_dir / "validate"
    validate_dir.mkdir(parents=True, exist_ok=True)
    extra_env = skill_evaluator_env(settings)
    with stage_skill_for_evaluator(projected_dir) as (staged, staging_root):
        try:
            proc = _run(
                resolved,
                [
                    "quality-check",
                    str(staged),
                    "-r",
                    "json",
                    "-o",
                    str(quality_dir),
                ],
                cwd=staging_root,
                timeout=settings.quality_timeout_sec,
                extra_env=extra_env,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            results.append(
                NvidiaSkillResult(
                    skill_id=label,
                    command="quality-check",
                    skipped=True,
                    skip_reason=str(exc),
                )
            )
            return results

        score, grade = _parse_quality(quality_dir)
        unavailable = judge_unavailable(quality_dir, proc.stdout, proc.stderr)
        skipped = unavailable or score is None
        skip_reason = None
        if unavailable:
            skip_reason = "SkillEvaluator quality LLM unavailable (EOL or missing model)"
        elif score is None:
            skip_reason = "quality-check produced no score"
        results.append(
            NvidiaSkillResult(
                skill_id=label,
                command="quality-check",
                exit_code=proc.returncode,
                skipped=skipped,
                skip_reason=skip_reason,
                stdout=proc.stdout[-8000:],
                stderr=proc.stderr[-8000:],
                report_files=[str(p) for p in quality_dir.glob("*")],
                quality_score=None if skipped else score,
                quality_grade=None if skipped else grade,
                dimensions=parse_quality_dimensions(quality_dir),
            )
        )

        try:
            vproc = _run(
                resolved,
                [
                    "validate",
                    str(staged),
                    "--checks",
                    settings.checks,
                    "--no-dedup",
                    "--continue-on-failure",
                    "-r",
                    "json",
                    "-o",
                    str(validate_dir),
                ],
                cwd=staging_root,
                timeout=settings.validate_timeout_sec,
                extra_env=extra_env,
            )
            results.append(
                NvidiaSkillResult(
                    skill_id=label,
                    command="validate",
                    exit_code=vproc.returncode,
                    stdout=vproc.stdout[-8000:],
                    stderr=vproc.stderr[-8000:],
                    report_files=[str(p) for p in validate_dir.glob("*")],
                    schema_high=parse_schema_high(validate_dir),
                )
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
            results.append(
                NvidiaSkillResult(
                    skill_id=label,
                    command="validate",
                    skipped=True,
                    skip_reason=str(exc),
                )
            )
    return results


def _report_files(report_dir: Path) -> list[str]:
    """Return JSON paths under ``report_dir`` as strings."""
    return [str(path) for path in sorted({p.resolve() for p in report_dir.glob("**/*.json")})]


def _hydrate_quality(skill_id: str, report_dir: Path) -> NvidiaSkillResult | None:
    """Build a quality-check row from an existing report directory."""
    if not report_dir.is_dir() or not _iter_json(report_dir):
        return None
    score, grade = _parse_quality(report_dir)
    unavailable = judge_unavailable(report_dir)
    skipped = unavailable or score is None
    reason = None
    if unavailable and score is None:
        reason = "SkillEvaluator quality LLM unavailable (EOL or missing model)"
    elif score is None:
        reason = "quality-check produced no score"
    return NvidiaSkillResult(
        skill_id=skill_id,
        command="quality-check",
        skipped=skipped,
        skip_reason=reason,
        report_files=_report_files(report_dir),
        quality_score=None if skipped else score,
        quality_grade=None if skipped else grade,
        dimensions=parse_quality_dimensions(report_dir),
    )


def _hydrate_validate(skill_id: str, report_dir: Path) -> NvidiaSkillResult | None:
    """Build a validate row from an existing report directory."""
    if not report_dir.is_dir() or not _iter_json(report_dir):
        return None
    return NvidiaSkillResult(
        skill_id=skill_id,
        command="validate",
        skipped=False,
        report_files=_report_files(report_dir),
        schema_high=parse_schema_high(report_dir),
    )


def _hydrate_rubric(skill_id: str, report_dir: Path) -> NvidiaSkillResult | None:
    """Build a rubric-eval row from an existing report directory."""
    if not report_dir.is_dir() or not _iter_json(report_dir):
        return None
    score, criteria = parse_rubric(report_dir)
    unavailable = judge_unavailable(report_dir)
    if score is not None:
        return NvidiaSkillResult(
            skill_id=skill_id,
            command="rubric-eval",
            skipped=False,
            report_files=_report_files(report_dir),
            rubric_score=score,
            rubric_criteria=criteria,
            quality_score=score,
        )
    reason = "rubric-eval produced no score"
    if unavailable:
        reason = "SkillEvaluator rubric LLM unavailable (EOL or missing model)"
    return NvidiaSkillResult(
        skill_id=skill_id,
        command="rubric-eval",
        skipped=True,
        skip_reason=reason,
        report_files=_report_files(report_dir),
        rubric_score=None,
        rubric_criteria=criteria,
    )


def _hydrate_similarity(skill_id: str, report_dir: Path) -> NvidiaSkillResult | None:
    """Build a similarity-check row from an existing report directory."""
    if not report_dir.is_dir() or not _iter_json(report_dir):
        return None
    pairs = parse_similarity_pairs(report_dir)
    unavailable = judge_unavailable(report_dir)
    if pairs is not None:
        return NvidiaSkillResult(
            skill_id=skill_id,
            command="similarity-check",
            skipped=False,
            report_files=_report_files(report_dir),
            similarity_pairs=pairs,
        )
    reason = "similarity-check produced no usable pair count"
    if unavailable:
        reason = "SkillEvaluator embedding model unavailable (EOL or missing model)"
    return NvidiaSkillResult(
        skill_id=skill_id,
        command="similarity-check",
        skipped=True,
        skip_reason=reason,
        report_files=_report_files(report_dir),
        similarity_pairs=None,
    )


def hydrate_nvidia_from_reports(run_dir: Path) -> list[NvidiaSkillResult]:
    """Re-parse SkillEvaluator JSON already on disk into NVIDIA result rows.

    Recovers scores that a prior parser missed without re-invoking the CLI.
    """
    rows: list[NvidiaSkillResult] = []
    nvidia_root = run_dir / "nvidia"
    if not nvidia_root.is_dir():
        return rows
    for arm, suffix in (("baseline", ""), ("improved", "#improved")):
        arm_root = nvidia_root / arm
        if not arm_root.is_dir():
            continue
        for corpus_dir in sorted(p for p in arm_root.iterdir() if p.is_dir()):
            for skill_dir in sorted(p for p in corpus_dir.iterdir() if p.is_dir()):
                skill_id = f"{corpus_dir.name}/{skill_dir.name}{suffix}"
                quality = _hydrate_quality(skill_id, skill_dir / "quality")
                if quality is not None:
                    rows.append(quality)
                validate = _hydrate_validate(skill_id, skill_dir / "validate")
                if validate is not None:
                    rows.append(validate)
                rubric = _hydrate_rubric(skill_id, skill_dir / "rubric")
                if rubric is not None:
                    rows.append(rubric)
    tier2 = nvidia_root / "tier2"
    if tier2.is_dir():
        for corpus_dir in sorted(p for p in tier2.iterdir() if p.is_dir()):
            similarity = _hydrate_similarity(corpus_dir.name, corpus_dir)
            if similarity is not None:
                rows.append(similarity)
    return rows

