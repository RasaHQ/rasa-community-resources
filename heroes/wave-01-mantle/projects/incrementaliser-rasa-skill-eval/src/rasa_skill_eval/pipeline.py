"""Inventory, project, NVIDIA tiers, LLM improver, then write run artifacts."""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval.config import AppConfig, load_config
from rasa_skill_eval.corpus import fetch_all
from rasa_skill_eval.improver import improve_projected_skill
from rasa_skill_eval.llm import try_backup_improver_client, try_client
from rasa_skill_eval.llm.openai_compat import DEFAULT_CIRCUIT
from rasa_skill_eval.models import (
    DeepEvalResult,
    ImproverDelta,
    IntegrationIssue,
    MantleInventory,
    NvidiaSkillResult,
    ProjectionSidecar,
    TsrRun,
)
from rasa_skill_eval.nvidia_llm import (
    nvidia_key_configured,
    rubric_eval_skill,
    similarity_check_collection,
)
from rasa_skill_eval.nvidia_runner import (
    evaluate_skill,
    hydrate_nvidia_from_reports,
    nvidia_command_successful,
    resolve_skillevaluator,
)
from rasa_skill_eval.persist import (
    atomic_write_json,
    improver_mode_counts,
    improver_mode_label,
    load_json_object,
)
from rasa_skill_eval.progress import progress_mark
from rasa_skill_eval.projector import example_lines_for_skill, load_sidecar, project_skill
from rasa_skill_eval.rasa_static import inventory_skill
from rasa_skill_eval.report import write_improver_delta
from rasa_skill_eval.runs import make_run_dir
from rasa_skill_eval.scope import tag_inventory
from rasa_skill_eval.skill_io import discover_skill_dirs


def _corpus_ready(config: AppConfig) -> bool:
    """Return True when the primary Rasano tree is present."""
    rasano = config.resolve(config.corpora["rasano"].dest)
    return rasano.is_dir() and (rasano / "skills").is_dir()


def _agent_roots(config: AppConfig) -> list[tuple[str, Path]]:
    """Return named Mantle agent project roots to scan."""
    roots: list[tuple[str, Path]] = []
    for name in ("rasano", "personalization"):
        entry = config.corpora.get(name)
        if entry is None:
            continue
        path = config.resolve(entry.dest)
        if path.is_dir():
            roots.append((name, path))
    return roots


def discover_first_skill(config: AppConfig) -> str | None:
    """Return the first discovered skill key (e.g. 'rasano/banking-faq') using stable ordering."""
    for corpus_name, agent_root in _agent_roots(config):
        skills_root = agent_root / "skills"
        scan = skills_root if skills_root.is_dir() else agent_root
        dirs = discover_skill_dirs(scan)
        if dirs:
            return f"{corpus_name}/{kebab_safe(dirs[0].name)}"
    return None


def kebab_safe(skill_id: str) -> str:
    """Folder name for a projected skill."""
    return skill_id.replace("_", "-").lower()


def _quality_for(skill_id: str, results: list[NvidiaSkillResult]) -> float | None:
    """Return the latest quality-check score for ``skill_id``."""
    for item in reversed(results):
        if (
            item.skill_id == skill_id
            and item.command == "quality-check"
            and item.quality_score is not None
        ):
            return item.quality_score
    return None


def _apply_delta_quality(
    delta: ImproverDelta,
    skill_key: str,
    imp_key: str,
    nvidia_results: list[NvidiaSkillResult],
    imp_results: list[NvidiaSkillResult],
) -> ImproverDelta:
    """Set baseline/improved quality from this call, then hydrated NVIDIA rows.

    Resume can return an empty ``imp_results`` when quality-check already
    exists on disk; those scores still live on ``nvidia_results``.
    """
    delta.baseline_quality = _quality_for(skill_key, nvidia_results)
    improved = _quality_for(imp_key, imp_results)
    if improved is None:
        improved = _quality_for(imp_key, nvidia_results)
    delta.improved_quality = improved
    return delta


def _score_projected(
    dest: Path,
    nvidia_out: Path,
    cfg: AppConfig,
    skill_key: str,
    *,
    existing_results: list[NvidiaSkillResult] | None = None,
    require_rubric: bool = True,
) -> list[NvidiaSkillResult]:
    """Run missing T1 quality/validate and optional rubric on one projection."""
    existing_successful = {
        item.command
        for item in (existing_results or [])
        if item.skill_id == skill_key and nvidia_command_successful(item)
    }
    rows: list[NvidiaSkillResult] = []
    # If both quality-check and validate are already present and successful, keep existing
    if "quality-check" not in existing_successful or "validate" not in existing_successful:
        rows.extend(evaluate_skill(dest, nvidia_out, cfg.nvidia, skill_id=skill_key))
    if require_rubric and nvidia_key_configured() and "rubric-eval" not in existing_successful:
        rows.append(
            rubric_eval_skill(
                dest,
                nvidia_out / "rubric",
                cfg.nvidia,
                skill_id=skill_key,
                judge=cfg.llm.judge,
            )
        )
    return rows


def _should_rewrite_skill(
    dest: Path,
    corpus_name: str,
    skill_name: str,
    deltas: list[ImproverDelta],
    *,
    reimprove: bool = False,
    retry_degraded: bool = False,
) -> bool:
    """Return whether this skill needs improver execution."""
    if reimprove:
        return True
    skill_key = f"{corpus_name}/{skill_name}"
    improved = dest / "improved" / corpus_name / skill_name / "SKILL.md"
    if not improved.is_file() or not improved.read_text(encoding="utf-8").strip():
        return True
    if retry_degraded:
        for delta in deltas:
            if delta.skill_id != skill_key:
                continue
            if delta.degraded:
                return True
            if any("SCHEMA HIGH" in change for change in delta.changes):
                return True
    return False


def _layer_a_skill_complete(
    dest: Path,
    corpus_name: str,
    skill_name: str,
    nvidia_results: list[NvidiaSkillResult],
    *,
    require_rubric: bool = False,
) -> bool:
    """Return whether every required Layer A result exists successfully."""
    skill_key = f"{corpus_name}/{skill_name}"
    improved = dest / "improved" / corpus_name / skill_name / "SKILL.md"
    projected = dest / "projected" / corpus_name / skill_name / "SKILL.md"
    if not improved.is_file() or not projected.is_file():
        return False
    required = {"quality-check", "validate"}
    if require_rubric:
        required.add("rubric-eval")
    base_commands = {
        item.command
        for item in nvidia_results
        if item.skill_id == skill_key and nvidia_command_successful(item)
    }
    improved_commands = {
        item.command
        for item in nvidia_results
        if item.skill_id == f"{skill_key}#improved" and nvidia_command_successful(item)
    }
    return required <= base_commands and required <= improved_commands


def _merge_missing_nvidia(
    existing: list[NvidiaSkillResult],
    incoming: list[NvidiaSkillResult],
    skill_id: str,
) -> list[NvidiaSkillResult]:
    """Replace only absent or skipped NVIDIA commands for one skill."""
    successful = {
        item.command
        for item in existing
        if item.skill_id == skill_id and nvidia_command_successful(item)
    }
    commands_to_replace = {
        item.command for item in incoming if item.command not in successful
    }
    kept = [
        item
        for item in existing
        if not (item.skill_id == skill_id and item.command in commands_to_replace)
    ]
    kept.extend(item for item in incoming if item.command in commands_to_replace)
    return kept


def _schema_high_messages(results: list[NvidiaSkillResult], skill_key: str) -> list[str]:
    """Collect SCHEMA HIGH messages for one skill id."""
    found: list[str] = []
    for item in results:
        if item.skill_id != skill_key or item.command != "validate":
            continue
        found.extend(item.schema_high)
    return found


def _delta_from_disk(
    dest: Path,
    skill_key: str,
    existing: list[ImproverDelta],
    *,
    mode: str,
) -> ImproverDelta:
    """Reuse a stored improver row or synthesize one from on-disk SKILL.md."""
    for delta in existing:
        if delta.skill_id == skill_key:
            return delta
    corpus, _, skill_name = skill_key.partition("/")
    original = dest / "projected" / corpus / skill_name / "SKILL.md"
    improved = dest / "improved" / corpus / skill_name / "SKILL.md"
    original_text = original.read_text(encoding="utf-8") if original.is_file() else ""
    improved_text = improved.read_text(encoding="utf-8") if improved.is_file() else ""
    return ImproverDelta(
        skill_id=skill_key,
        baseline_skill_md_words=len(original_text.split()),
        improved_skill_md_words=len(improved_text.split()),
        constraints_preserved=True,
        changes=["reused on-disk improved skill"],
        mode=mode,
        degraded=False,
    )


def seed_imported_layer_a(source: Path, dest: Path) -> list[ImproverDelta]:
    """Copy projected/improved packages and improver rows into a new run folder.

    Does not copy agents, coverage, TSR, or Windows NVIDIA report paths.
    """
    source = source.resolve()
    dest = dest.resolve()
    projected = source / "projected"
    improved = source / "improved"
    if not projected.is_dir() or not improved.is_dir():
        raise FileNotFoundError(
            f"{source} must contain projected/ and improved/ to seed run-all2"
        )
    dest.mkdir(parents=True, exist_ok=True)
    dest_projected = dest / "projected"
    dest_improved = dest / "improved"
    if dest_projected.exists():
        shutil.rmtree(dest_projected)
    if dest_improved.exists():
        shutil.rmtree(dest_improved)
    shutil.copytree(projected, dest_projected)
    shutil.copytree(improved, dest_improved)
    payload = load_run_payload(source)
    deltas = deltas_from_payload(payload)
    if not deltas:
        raise FileNotFoundError(f"{source}/results.json has no improver rows")
    missing: list[str] = []
    for delta in deltas:
        corpus, _, skill_name = delta.skill_id.partition("/")
        skill_md = dest_improved / corpus / skill_name / "SKILL.md"
        if not skill_md.is_file():
            missing.append(delta.skill_id)
    if missing:
        raise FileNotFoundError(
            "Imported improved SKILL.md missing for: " + ", ".join(missing)
        )
    atomic_write_json(
        dest / "results.json",
        {
            "meta": {
                "interrupted": False,
                "imported_from": str(source),
                "kimi_skipped": True,
            },
            "improver": [item.model_dump(mode="json") for item in deltas],
            "nvidia": [],
            "sidecars": payload.get("sidecars") or [],
            "inventories": payload.get("inventories") or [],
        },
    )
    return deltas


def run_pipeline(
    config: AppConfig | None = None,
    fetch: bool = True,
    run_dir: Path | None = None,
    reimprove: bool = False,
    retry_degraded: bool = False,
    retry_incomplete: bool = False,
    only_skill_key: str | None = None,
    skip_improver: bool = False,
    preserve_projections: bool = False,
) -> Path:
    """Run skill-eval and return the dated run directory.

    If ``only_skill_key`` is set (e.g. "rasano/block-card"), only that skill is processed.
    ``skip_improver`` never calls the LLM; missing improved SKILL.md fails the skill.
    ``preserve_projections`` keeps existing projected/improved packages (run-all2).
    """
    load_dotenv()
    cfg = config or load_config()
    if fetch and not _corpus_ready(cfg):
        logger.info("Corpus missing; fetching pinned sources")
        fetch_all(cfg)
    dest = run_dir or make_run_dir("heroes_eval", cfg.runs_root())
    dest.mkdir(parents=True, exist_ok=True)
    if retry_incomplete:
        logger.info(
            "Retrying incomplete Layer A NVIDIA commands "
            "(null/failed quality, rubric, and T2 scores count as incomplete)"
        )
    sink_id = logger.add(dest / "pipeline.log", level="INFO")
    logger.info("Run directory: {}", dest)
    logger.info(
        "Native Mantle skills are not SkillEvaluator input; scoring projected copies only"
    )
    DEFAULT_CIRCUIT.reset()
    DEFAULT_CIRCUIT.trip_after = max(1, cfg.eval.llm_rate_limit_trip_after)

    existing = load_run_payload(dest)
    inventories: list[MantleInventory] = inventories_from_payload(existing)
    sidecars: list[ProjectionSidecar] = [
        ProjectionSidecar.model_validate(row) for row in existing.get("sidecars") or []
    ]
    nvidia_results: list[NvidiaSkillResult] = nvidia_from_payload(existing)
    hydrated = hydrate_nvidia_from_reports(dest)
    if hydrated:
        by_skill: dict[str, list[NvidiaSkillResult]] = {}
        for item in hydrated:
            by_skill.setdefault(item.skill_id, []).append(item)
        for skill_id, rows in by_skill.items():
            nvidia_results = _merge_missing_nvidia(nvidia_results, rows, skill_id)
        logger.info(
            "Hydrated {} NVIDIA command rows from on-disk SkillEvaluator reports",
            len(hydrated),
        )
    deltas: list[ImproverDelta] = deltas_from_payload(existing)

    projected_root = dest / "projected"
    improved_root = dest / "improved"
    nvidia_root = dest / "nvidia"
    client = None if skip_improver else try_client(cfg.llm.improver)
    backup_client = None if skip_improver else try_backup_improver_client(cfg.llm.improver)
    writing_dir = cfg.resolve(cfg.paths.writing_for_agents_dir)
    unslop_dir = cfg.resolve(cfg.paths.unslop_dir)
    cache_root = cfg.runs_root() / ".improver-cache"
    improver_model_id = cfg.llm.improver.path_id()
    done_skills = {item.skill_id for item in deltas}

    try:
        if hydrated:
            _flush_layer_a(
                dest,
                cfg,
                inventories,
                sidecars,
                nvidia_results,
                deltas,
                client is not None,
            )
        for corpus_name, agent_root in _agent_roots(cfg):
            skills_root = agent_root / "skills"
            scan = skills_root if skills_root.is_dir() else agent_root
            for skill_dir in discover_skill_dirs(scan):
                dest_skill = projected_root / corpus_name / kebab_safe(skill_dir.name)
                skill_key = f"{corpus_name}/{dest_skill.name}"
                if only_skill_key is not None and skill_key != only_skill_key:
                    continue
                progress_key = f"skill:{skill_key}"
                should_rewrite = _should_rewrite_skill(
                    dest,
                    corpus_name,
                    dest_skill.name,
                    deltas,
                    reimprove=reimprove,
                    retry_degraded=retry_degraded,
                )
                if (
                    not should_rewrite
                    and skill_key in done_skills
                    and _layer_a_skill_complete(
                        dest,
                        corpus_name,
                        dest_skill.name,
                        nvidia_results,
                        require_rubric=nvidia_key_configured(),
                    )
                ):
                    logger.info("Resume skip Layer A {}", skill_key)
                    progress_mark(
                        progress_key,
                        "layer_a",
                        "complete",
                        message=f"Reused {skill_key}",
                    )
                    continue
                progress_mark(progress_key, "layer_a", "running", message=f"Scoring {skill_key}")
                inv = inventory_skill(skill_dir, project_root=agent_root)
                inv.skill_id = f"{corpus_name}/{skill_dir.name}"
                inv.scopes = tag_inventory(inv, agent_root)
                inventories = [item for item in inventories if item.skill_id != inv.skill_id]
                inventories.append(inv)
                if preserve_projections and (dest_skill / "SKILL.md").is_file():
                    sidecar = load_sidecar(dest_skill) or ProjectionSidecar(
                        source_skill_id=skill_dir.name,
                        source_display_name=skill_dir.name,
                        projected_name=dest_skill.name,
                        source_path=str(skill_dir),
                        projected_path=str(dest_skill),
                    )
                else:
                    examples = example_lines_for_skill(
                        cfg.resolve(cfg.paths.data_dir),
                        corpus_name,
                        skill_dir.name,
                    )
                    sidecar = project_skill(
                        skill_dir,
                        dest_skill,
                        cfg.projection,
                        example_lines=examples,
                    )
                sidecars = [
                    item
                    for item in sidecars
                    if item.projected_path != sidecar.projected_path
                ]
                sidecars.append(sidecar)
                nvidia_out = nvidia_root / "baseline" / corpus_name / dest_skill.name
                t0_skill = time.perf_counter()
                try:
                    t0_eval = time.perf_counter()
                    baseline_results = _score_projected(
                        dest_skill,
                        nvidia_out,
                        cfg,
                        skill_key,
                        existing_results=nvidia_results,
                        require_rubric=nvidia_key_configured(),
                    )
                    nvidia_results = _merge_missing_nvidia(
                        nvidia_results, baseline_results, skill_key
                    )
                    logger.info(
                        "Baseline NVIDIA eval for {} took {:.2f}s",
                        skill_key,
                        time.perf_counter() - t0_eval,
                    )

                    improved = improved_root / corpus_name / dest_skill.name
                    should_rewrite = _should_rewrite_skill(
                        dest,
                        corpus_name,
                        dest_skill.name,
                        deltas,
                        reimprove=reimprove,
                        retry_degraded=retry_degraded,
                    )
                    if skip_improver:
                        should_rewrite = False
                        if not (improved / "SKILL.md").is_file():
                            raise FileNotFoundError(
                                f"Imported improved SKILL.md missing for {skill_key}"
                            )
                    delta: ImproverDelta | None = None
                    if not should_rewrite:
                        delta = _delta_from_disk(
                            dest,
                            skill_key,
                            deltas,
                            mode="imported" if skip_improver else "cached",
                        )
                        if any(item.skill_id == skill_key for item in deltas):
                            logger.info("Reused improved skill for {}", skill_key)
                    if delta is None:
                        t0_imp = time.perf_counter()
                        delta = improve_projected_skill(
                            dest_skill,
                            improved,
                            cfg.projection,
                            client=client,
                            backup_client=backup_client,
                            writing_for_agents_dir=writing_dir if writing_dir.is_dir() else None,
                            unslop_dir=unslop_dir if unslop_dir.is_dir() else None,
                            cache_dir=cache_root,
                            cache_id=skill_key,
                            reimprove=reimprove or retry_degraded,
                            improver_model_id=improver_model_id,
                        )
                        logger.info(
                            "Improver rewrite for {} took {:.2f}s (mode={})",
                            skill_key,
                            time.perf_counter() - t0_imp,
                            delta.mode,
                        )

                    delta.skill_id = skill_key
                    nvidia_imp = nvidia_root / "improved" / corpus_name / dest_skill.name
                    imp_key = f"{skill_key}#improved"
                    t0_imp_eval = time.perf_counter()
                    imp_results = _score_projected(
                        improved,
                        nvidia_imp,
                        cfg,
                        imp_key,
                        existing_results=nvidia_results,
                        require_rubric=nvidia_key_configured(),
                    )
                    logger.info(
                        "Improved NVIDIA eval for {} took {:.2f}s",
                        skill_key,
                        time.perf_counter() - t0_imp_eval,
                    )
                    _apply_delta_quality(
                        delta, skill_key, imp_key, nvidia_results, imp_results
                    )
                    schema_high = _schema_high_messages(imp_results, imp_key)
                    if schema_high:
                        delta.changes.append("SCHEMA HIGH: " + "; ".join(schema_high))

                    quality_dropped = (
                        delta.baseline_quality is not None
                        and delta.improved_quality is not None
                        and delta.improved_quality < delta.baseline_quality
                    )
                    # Degradation check: retry 1 more time using backup model only if rewriting.
                    if (
                        should_rewrite
                        and backup_client is not None
                        and (quality_dropped or schema_high)
                    ):
                        backup_model_name = getattr(cfg.llm.improver, "backup_model", "backup")
                        logger.warning(
                            "Retrying improver with backup model {} for {} "
                            "(quality drop={}, schema_high={})",
                            backup_model_name,
                            skill_key,
                            quality_dropped,
                            bool(schema_high),
                        )
                        retry_delta = improve_projected_skill(
                            dest_skill,
                            improved,
                            cfg.projection,
                            client=backup_client,
                            writing_for_agents_dir=writing_dir if writing_dir.is_dir() else None,
                            unslop_dir=unslop_dir if unslop_dir.is_dir() else None,
                            cache_dir=None,
                            cache_id=skill_key,
                            reimprove=True,
                            improver_model_id=backup_model_name,
                        )
                        retry_delta.skill_id = skill_key
                        retry_imp_results = _score_projected(
                            improved, nvidia_imp, cfg, imp_key
                        )
                        _apply_delta_quality(
                            retry_delta,
                            skill_key,
                            imp_key,
                            nvidia_results,
                            retry_imp_results,
                        )
                        retry_delta.baseline_quality = delta.baseline_quality
                        retry_quality = retry_delta.improved_quality
                        retry_high = _schema_high_messages(retry_imp_results, imp_key)
                        if retry_high:
                            retry_delta.changes.append(
                                "SCHEMA HIGH: " + "; ".join(retry_high)
                            )
                        quality_ok = (
                            retry_quality is not None
                            and delta.baseline_quality is not None
                            and retry_quality >= delta.baseline_quality
                        )
                        if quality_ok and not retry_high:
                            logger.info(
                                "Backup improver achieved improvement: {:.1f} >= {:.1f}",
                                retry_quality,
                                delta.baseline_quality,
                            )
                            delta = retry_delta
                            imp_results = retry_imp_results
                            delta.degraded = False
                        else:
                            logger.warning(
                                "Backup improver retry still degraded for {}",
                                skill_key,
                            )
                            delta.degraded = True
                    elif quality_dropped or schema_high:
                        delta.degraded = True
                    nvidia_results = _merge_missing_nvidia(
                        nvidia_results, imp_results, imp_key
                    )
                    deltas = [item for item in deltas if item.skill_id != skill_key]
                    deltas.append(delta)
                    done_skills.add(skill_key)
                    progress_mark(
                        progress_key, "layer_a", "complete", message=f"Completed {skill_key}"
                    )
                    logger.info(
                        "Total processing for {} took {:.2f}s",
                        skill_key,
                        time.perf_counter() - t0_skill,
                    )
                except Exception as exc:
                    logger.exception("Skill {} failed; continuing: {}", skill_key, exc)
                    progress_mark(
                        progress_key,
                        "layer_a",
                        "failed",
                        message=f"Failed {skill_key}",
                        reason=str(exc),
                    )
                _flush_layer_a(
                    dest,
                    cfg,
                    inventories,
                    sidecars,
                    nvidia_results,
                    deltas,
                    client is not None,
                )

        for corpus_name, _agent_root in _agent_roots(cfg):
            collection = projected_root / corpus_name
            if collection.is_dir() and nvidia_key_configured():
                already = any(
                    item.command == "similarity-check"
                    and item.skill_id == collection.name
                    and nvidia_command_successful(item)
                    for item in nvidia_results
                )
                if already:
                    continue
                try:
                    nvidia_results.append(
                        similarity_check_collection(
                            collection,
                            nvidia_root / "tier2" / corpus_name,
                            cfg.nvidia,
                        )
                    )
                except Exception as exc:
                    logger.exception(
                        "Tier 2 similarity for {} failed; continuing: {}",
                        corpus_name,
                        exc,
                    )

        _flush_layer_a(
            dest,
            cfg,
            inventories,
            sidecars,
            nvidia_results,
            deltas,
            client is not None,
        )
        write_improver_delta(dest / "IMPROVER_DELTA.md", deltas)
        return dest
    finally:
        logger.remove(sink_id)


def _layer_a_payload(
    cfg: AppConfig,
    inventories: list[MantleInventory],
    sidecars: list[ProjectionSidecar],
    nvidia_results: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    *,
    improver_client: bool,
) -> dict[str, Any]:
    """Build the Layer A slice of ``results.json``."""
    return {
        "meta": {
            "rasa_pro_version": cfg.project.rasa_pro_version,
            "engine": cfg.project.engine,
            "skillevaluator": resolve_skillevaluator() is not None,
            "nvidia_key": nvidia_key_configured(),
            "improver_mode": improver_mode_label(deltas, client_available=improver_client),
            "improver_counts": improver_mode_counts(deltas),
            "projection_required": True,
            "note": "NVIDIA scores are on projected Agent Skills copies, not native skill.md",
        },
        "inventories": [i.model_dump(mode="json") for i in inventories],
        "sidecars": [s.model_dump(mode="json") for s in sidecars],
        "nvidia": [n.model_dump(mode="json") for n in nvidia_results],
        "improver": [d.model_dump(mode="json") for d in deltas],
    }


def _flush_layer_a(
    dest: Path,
    cfg: AppConfig,
    inventories: list[MantleInventory],
    sidecars: list[ProjectionSidecar],
    nvidia_results: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    improver_client: bool,
) -> None:
    """Write Layer A fields into ``results.json``, keeping any Layer B keys already present."""
    payload = _layer_a_payload(
        cfg,
        inventories,
        sidecars,
        nvidia_results,
        deltas,
        improver_client=improver_client,
    )
    merge_run_payload(dest, payload)


def merge_run_payload(run_dir: Path, updates: dict[str, Any]) -> dict[str, Any]:
    """Merge ``updates`` into ``results.json``. ``meta`` keys are shallow-merged."""
    payload = load_run_payload(run_dir)
    if "meta" in updates and isinstance(updates["meta"], dict):
        meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
        merged_meta = dict(meta)
        merged_meta.update(updates["meta"])
        updates = {**updates, "meta": merged_meta}
    payload.update(updates)
    atomic_write_json(run_dir / "results.json", payload)
    return payload


def load_run_payload(run_dir: Path) -> dict[str, Any]:
    """Load ``results.json`` from a run folder."""
    return load_json_object(run_dir / "results.json")


def inventories_from_payload(payload: dict[str, Any]) -> list[MantleInventory]:
    """Map stored inventories back to models."""
    return [MantleInventory.model_validate(row) for row in payload.get("inventories") or []]


def nvidia_from_payload(payload: dict[str, Any]) -> list[NvidiaSkillResult]:
    """Map stored NVIDIA rows back to models."""
    return [NvidiaSkillResult.model_validate(row) for row in payload.get("nvidia") or []]


def deltas_from_payload(payload: dict[str, Any]) -> list[ImproverDelta]:
    """Map stored improver rows back to models."""
    return [ImproverDelta.model_validate(row) for row in payload.get("improver") or []]


def tsr_from_payload(payload: dict[str, Any]) -> list[TsrRun]:
    """Map stored TSR rows back to models."""
    return [TsrRun.model_validate(row) for row in payload.get("tsr") or []]


def deepeval_from_payload(payload: dict[str, Any]) -> list[DeepEvalResult]:
    """Map stored DeepEval rows back to models."""
    return [DeepEvalResult.model_validate(row) for row in payload.get("deepeval") or []]


def issues_from_payload(payload: dict[str, Any]) -> list[IntegrationIssue]:
    """Map stored integration issues back to models."""
    return [IntegrationIssue.model_validate(row) for row in payload.get("integration_issues") or []]
