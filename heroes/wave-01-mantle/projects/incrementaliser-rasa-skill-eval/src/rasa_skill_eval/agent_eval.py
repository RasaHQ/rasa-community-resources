"""Prepare native vs improved agent trees and score weighted TSR."""

from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from subprocess import CompletedProcess
from typing import Any

import yaml
from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval.config import AppConfig, LlmEndpointSettings, load_config
from rasa_skill_eval.local_llm import ensure_local_actor, stop_local_actors
from rasa_skill_eval.models import IntegrationIssue, ObservedTrace, TsrRun
from rasa_skill_eval.persist import (
    atomic_write_json,
    load_coverage,
    save_coverage,
    set_coverage_unit,
    text_sha256,
    tree_sha256,
    tsr_identity,
    unit_status,
    upsert_issues,
    upsert_tsr,
)
from rasa_skill_eval.pipeline import (
    issues_from_payload,
    load_run_payload,
    merge_run_payload,
    tsr_from_payload,
)
from rasa_skill_eval.proc import CommandTimeout, run_captured
from rasa_skill_eval.progress import progress_mark
from rasa_skill_eval.rasa_live import RasaRestServer, run_scenario_live
from rasa_skill_eval.remerge import (
    AGENT_SKILLS_HEADING_ASK,
    REMERGE_SCHEMA,
    SESSION_PROSE_ASK,
    UNKNOWN_STEP_ASK,
    apply_session_prose_workaround,
    apply_unknown_step_workaround,
    remerge_prose,
)
from rasa_skill_eval.runs import latest_run_dir, make_run_dir
from rasa_skill_eval.scenarios import load_scenarios, scenarios_dir
from rasa_skill_eval.skill_io import discover_skill_dirs
from rasa_skill_eval.tsr import score_observation

_OPENAI_KEY_RE = re.compile(r"\$\{OPENAI_API_KEY\}")
_LAYER_B_AGENTS = ("rasano", "personalization")
_TRAIN_LOG_TAIL = 4000
_TREE_SKIP_DIRS = frozenset({".venv", ".git", "models", "__pycache__", ".env"})
_TRAIN_SKIP_FILES = frozenset({"integrations.yml", "endpoints.yml", ".rasa_eval_tree"})
_TRAIN_PLACEHOLDER = LlmEndpointSettings(
    id="train-placeholder",
    provider="local",
    model="train-placeholder",
    base_url="http://127.0.0.1:9/v1",
)


def render_model_group(
    settings: LlmEndpointSettings,
    group_id: str = "orchestrator",
) -> dict[str, Any]:
    """Build a Mantle ``model_groups`` entry from YAML LLM settings."""
    provider = settings.provider.strip().lower()
    if provider == "nvidia":
        return {
            "id": group_id,
            "models": [
                {
                    "provider": "self-hosted",
                    "model": settings.model,
                    "api_base": settings.base_url or "https://integrate.api.nvidia.com/v1",
                    "api_key": "${NVIDIA_API_KEY}",
                }
            ],
        }
    if provider in {"local", "llama", "llamacpp", "llama.cpp"}:
        return {
            "id": group_id,
            "models": [
                {
                    "provider": "self-hosted",
                    "model": settings.model,
                    "api_base": settings.base_url or "${LLAMA_BASE_URL}",
                    "api_key": "${LOCAL_LLM_API_KEY}",
                }
            ],
        }
    if provider == "anthropic":
        return {
            "id": group_id,
            "models": [
                {
                    "provider": "anthropic",
                    "model": settings.model,
                    "api_key": "${ANTHROPIC_API_KEY}",
                }
            ],
        }
    return {
        "id": group_id,
        "models": [
            {
                "provider": "openai",
                "model": settings.model,
                "api_key": "${OPENAI_API_KEY}",
            }
        ],
    }


def render_embedding_group(settings: LlmEndpointSettings) -> dict[str, Any]:
    """Build the FAQ/reference embeddings group. NVIDIA uses the OpenAI-compatible NIM URL."""
    provider = settings.provider.strip().lower()
    if provider == "nvidia":
        return {
            "id": "embeddings",
            "models": [
                {
                    "provider": "openai",
                    "model": settings.model,
                    "api_base": settings.base_url or "https://integrate.api.nvidia.com/v1",
                    "api_key": "${NVIDIA_API_KEY}",
                }
            ],
        }
    return render_model_group(settings, group_id="embeddings")


def write_integrations(
    agent_root: Path,
    settings: LlmEndpointSettings,
    embeddings: LlmEndpointSettings | None = None,
) -> None:
    """Overwrite orchestrator (and optional embeddings) model groups."""
    path = agent_root / "integrations.yml"
    existing: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            existing = loaded
    existing["llm"] = {"model_group": "orchestrator"}
    groups = [render_model_group(settings)]
    if embeddings is not None:
        groups.append(render_embedding_group(embeddings))
    existing["model_groups"] = groups
    channels = existing.get("channels")
    if not isinstance(channels, dict):
        channels = {}
    channels["rest"] = {"enabled": True}
    inspector = channels.get("inspector")
    if isinstance(inspector, dict):
        inspector["enabled"] = False
        channels["inspector"] = inspector
    existing["channels"] = channels
    path.write_text(
        yaml.safe_dump(existing, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_endpoints(agent_root: Path, settings: LlmEndpointSettings) -> None:
    """Rewrite ``endpoints.yml`` so ``rasa train`` does not require ``OPENAI_API_KEY``."""
    path = agent_root / "endpoints.yml"
    existing: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            existing = loaded
    chat = render_model_group(settings)
    existing["nlg"] = {"type": "rephrase", "llm": {"model_group": chat["id"]}}
    existing["model_groups"] = [chat]
    path.write_text(
        yaml.safe_dump(existing, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_references_embeddings(agent_root: Path, group_id: str = "embeddings") -> None:
    """Point ``agent.yml`` FAQ indexing at a packaged embeddings model group."""
    path = agent_root / "agent.yml"
    existing: dict[str, Any] = {}
    if path.is_file():
        loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            existing = loaded
    refs = existing.get("references")
    if not isinstance(refs, dict):
        refs = {}
    refs["embeddings"] = group_id
    existing["references"] = refs
    path.write_text(
        yaml.safe_dump(existing, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def write_rest_credentials(agent_root: Path) -> None:
    """Ensure a REST connector file exists for ``rasa run --connector rest``."""
    path = agent_root / "credentials.yml"
    if path.is_file():
        return
    path.write_text("rest:\n", encoding="utf-8")


def sweep_openai_api_key(agent_root: Path) -> int:
    """Replace leftover ``${OPENAI_API_KEY}`` with NVIDIA key in text configs.

    Returns the number of files rewritten. Skips binary and lock files.
    """
    skip_names = {".venv", ".git", "models", "__pycache__", "uv.lock"}
    rewritten = 0
    for path in agent_root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in skip_names for part in path.parts):
            continue
        if path.suffix.lower() not in {".yml", ".yaml", ".env", ".md", ".toml", ".json", ".txt"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if "${OPENAI_API_KEY}" not in text:
            continue
        path.write_text(
            _OPENAI_KEY_RE.sub("${NVIDIA_API_KEY}", text),
            encoding="utf-8",
        )
        rewritten += 1
    return rewritten


def _rasa_env(shared_venv: Path | None = None) -> dict[str, str]:
    """Environment for ``uv run rasa`` in an agent copy."""
    load_dotenv()
    env = os.environ.copy()
    if shared_venv is not None:
        env["UV_PROJECT_ENVIRONMENT"] = str(shared_venv)
    return env


def _copy_agent(src: Path, dest: Path) -> None:
    """Copy a Mantle agent tree, dropping venvs and models."""
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(
        src,
        dest,
        ignore=shutil.ignore_patterns(".venv", ".git", "models", "__pycache__", ".env"),
    )


def _tree_stamp(src: Path, run_dir: Path, agent_id: str, arm: str) -> str:
    """Hash corpus, remerge schema, and improved SKILL.md files that feed this arm."""
    parts = [
        tree_sha256(src, skip_dir_names=_TREE_SKIP_DIRS),
        agent_id,
        arm,
        REMERGE_SCHEMA,
    ]
    if arm == "improved":
        improved = run_dir / "improved" / agent_id
        if improved.is_dir():
            parts.append(tree_sha256(improved, skip_dir_names=_TREE_SKIP_DIRS))
    return text_sha256(*parts)


def _lock_hash(agent_root: Path) -> str:
    """Hash uv.lock and pyproject.toml for shared venv reuse."""
    chunks: list[str] = []
    for name in ("uv.lock", "pyproject.toml"):
        path = agent_root / name
        chunks.append(path.read_text(encoding="utf-8") if path.is_file() else "")
    return text_sha256(*chunks)[:16]


def _shared_venv(run_dir: Path, agent_root: Path) -> Path:
    """Return the lock-hashed venv under ``runs/.venv-cache/``."""
    return run_dir.parent / ".venv-cache" / _lock_hash(agent_root)


def _train_fingerprint(agent_root: Path, extra: str = "") -> str:
    """Hash train inputs excluding actor LLM config that is stamped at run time."""
    return text_sha256(
        extra,
        tree_sha256(
            agent_root,
            skip_dir_names=_TREE_SKIP_DIRS,
            skip_file_names=_TRAIN_SKIP_FILES,
        ),
    )


def _copy_train_models(src: Path, dest: Path) -> None:
    """Copy a cached ``models/`` directory onto an agent tree."""
    dest_models = dest / "models"
    if dest_models.exists():
        shutil.rmtree(dest_models)
    if src.is_dir():
        shutil.copytree(src, dest_models)


def stamp_runtime_llm(
    agent_root: Path,
    model: LlmEndpointSettings,
    embeddings: LlmEndpointSettings | None,
) -> None:
    """Write the live actor endpoint after training."""
    write_integrations(agent_root, model, embeddings)
    write_endpoints(agent_root, model)


def prepare_agent_tree(
    run_dir: Path,
    config: AppConfig,
    *,
    agent_id: str,
    model: LlmEndpointSettings,
    arm: str,
) -> Path:
    """Copy one corpus into ``agents/<agent>/<model>/<arm>/`` and stamp LLM config."""
    entry = config.corpora.get(agent_id)
    if entry is None:
        raise FileNotFoundError(f"Corpus {agent_id} missing from config.yaml")
    src = config.resolve(entry.dest)
    if not src.is_dir():
        raise FileNotFoundError(f"{agent_id} corpus missing: {src}. Run uv run fetch-corpus.")
    model_id = model.path_id()
    dest = run_dir / "agents" / agent_id / model_id / arm
    stamp = _tree_stamp(src, run_dir, agent_id, arm)
    stamp_file = dest / ".rasa_eval_tree"
    if dest.is_dir() and stamp_file.is_file() and stamp_file.read_text(encoding="utf-8") == stamp:
        logger.info("Reusing agent tree {}", dest)
        return dest
    _copy_agent(src, dest)
    embeddings = config.llm.embeddings if agent_id == "rasano" else None
    write_integrations(dest, _TRAIN_PLACEHOLDER, embeddings)
    write_endpoints(dest, _TRAIN_PLACEHOLDER)
    if embeddings is not None:
        write_references_embeddings(dest)
    write_rest_credentials(dest)
    swept = sweep_openai_api_key(dest)
    if swept:
        logger.info("Swept OPENAI_API_KEY from {} files under {}", swept, dest)
    if arm == "improved":
        improved_proj = run_dir / "improved" / agent_id
        native_skills = dest / "skills"
        if improved_proj.is_dir() and native_skills.is_dir():
            for skill_dir in discover_skill_dirs(native_skills):
                kebab = skill_dir.name.replace("_", "-").lower()
                proj = improved_proj / kebab
                if (proj / "SKILL.md").is_file():
                    remerge_prose(skill_dir, proj)
                    logger.info("Reverse-merged {}/{}", agent_id, skill_dir.name)
    stamp_file.write_text(stamp, encoding="utf-8")
    return dest


def prepare_agent_trees(run_dir: Path, config: AppConfig) -> tuple[Path, Path]:
    """Backward-compatible helper: prepare Rasano native/improved for the first agent model."""
    agents = config.llm.agents
    if not agents:
        raise ValueError("config.llm.agents is empty")
    model = agents[0]
    native = prepare_agent_tree(run_dir, config, agent_id="rasano", model=model, arm="native")
    improved = prepare_agent_tree(run_dir, config, agent_id="rasano", model=model, arm="improved")
    _copy_scenarios(run_dir, config)
    return native, improved


def _copy_scenarios(run_dir: Path, config: AppConfig) -> Path:
    """Copy committed scenarios into the run folder."""
    shared = run_dir / "eval" / "scenarios"
    src_scenarios = scenarios_dir(config.resolve(config.paths.data_dir))
    if not src_scenarios.is_dir():
        return shared
    shared.mkdir(parents=True, exist_ok=True)
    for path in src_scenarios.rglob("*.yml"):
        rel = path.relative_to(src_scenarios)
        dest = shared / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, dest)
    return shared


def _rasa_ready(agent_root: Path) -> tuple[bool, str]:
    """Return whether this tree can run ``rasa train``."""
    load_dotenv()
    if not os.getenv("RASA_LICENSE", "").strip():
        return False, "RASA_LICENSE is not set"
    if shutil.which("uv") is None:
        return False, "uv not on PATH"
    if not (agent_root / "pyproject.toml").is_file():
        return False, "agent copy has no pyproject.toml"
    return True, "ok"


def _combined_output(proc: CompletedProcess[str]) -> str:
    """Join stderr then stdout for a captured command."""
    return f"{proc.stderr or ''}\n{proc.stdout or ''}"


def _output_tail(proc: CompletedProcess[str], n: int = _TRAIN_LOG_TAIL) -> str:
    """Return the last ``n`` characters of captured process output."""
    return _combined_output(proc)[-n:]


def _try_sync(
    agent_root: Path,
    timeout_sec: float | None = None,
    log_path: Path | None = None,
    shared_venv: Path | None = None,
) -> tuple[bool, str]:
    """``uv sync`` in the agent copy, skipped when the lock hash matches."""
    stamp = (shared_venv or (agent_root / ".venv")) / ".rasa_eval_sync"
    lock_h = _lock_hash(agent_root)
    ready = shared_venv.is_dir() if shared_venv is not None else (agent_root / ".venv").is_dir()
    if stamp.is_file() and stamp.read_text(encoding="utf-8").strip() == lock_h and ready:
        return True, "sync cache hit"
    try:
        sync = run_captured(
            ["uv", "sync", "--prerelease=allow"],
            cwd=agent_root,
            env=_rasa_env(shared_venv),
            timeout_sec=timeout_sec,
            log_path=log_path,
        )
    except CommandTimeout as exc:
        return False, str(exc)
    if sync.returncode != 0:
        return False, _output_tail(sync)
    stamp.parent.mkdir(parents=True, exist_ok=True)
    stamp.write_text(lock_h, encoding="utf-8")
    return True, "ok"


def _try_rasa_train(
    agent_root: Path,
    timeout_sec: float | None = None,
    log_path: Path | None = None,
    shared_venv: Path | None = None,
) -> tuple[bool, str]:
    """``uv run rasa train`` in the agent copy."""
    try:
        train = run_captured(
            ["uv", "run", "rasa", "train"],
            cwd=agent_root,
            env=_rasa_env(shared_venv),
            timeout_sec=timeout_sec,
            log_path=log_path,
        )
    except CommandTimeout as cop:
        return False, str(cop)
    if train.returncode != 0:
        return False, _output_tail(train)
    return True, "trained"


def parse_train_issues(
    output: str,
    *,
    agent_id: str,
    model_id: str,
    arm: str,
) -> list[IntegrationIssue]:
    """Turn ``rasa train`` logs into reportable integration issues."""
    issues: list[IntegrationIssue] = []
    json_rows = _json_objects_from_log(output)
    for row in json_rows:
        event = str(row.get("event") or "")
        message = str(
            row.get("event_msg") or row.get("message") or row.get("text") or ""
        ).strip()
        if not event and not message:
            continue
        blob = json.dumps(row, ensure_ascii=True)
        issues.append(
            _issue_from_train_text(
                message or blob,
                agent_id=agent_id,
                model_id=model_id,
                arm=arm,
                event=event,
                raw=blob[-_TRAIN_LOG_TAIL:],
            )
        )
    if not issues:
        issues.append(
            _issue_from_train_text(
                output,
                agent_id=agent_id,
                model_id=model_id,
                arm=arm,
                event="",
                raw=output[-_TRAIN_LOG_TAIL:],
            )
        )
    return issues


def _json_objects_from_log(text: str) -> list[dict[str, Any]]:
    """Parse JSON objects from log lines that contain them."""
    found: list[dict[str, Any]] = []
    for line in text.splitlines():
        stripped = line.strip()
        brace = stripped.find("{")
        if brace < 0:
            continue
        try:
            data = json.loads(stripped[brace:])
        except json.JSONDecodeError:
            continue
        if isinstance(data, dict):
            found.append(data)
    return found


def is_session_prose_error(text: str) -> bool:
    """Return True when Mantle rejected ``session.*`` in instruction prose."""
    lower = text.lower()
    return "instruction prose" in lower and "session." in lower


def is_heading_train_error(text: str) -> bool:
    """Return True when train failed on markdown headings in ``skill.md``."""
    lower = text.lower()
    heading_tokens = (
        "heading",
        "## instructions",
        "## examples",
        "unexpected section",
        "unknown section",
        "agent skills",
    )
    if not any(token in lower for token in heading_tokens):
        return False
    return "skill.md" in lower or "skill markdown" in lower or "heading" in lower


def is_unknown_step_error(text: str) -> bool:
    """Return True when Mantle rejected an unknown ordered_block step property."""
    lower = text.lower()
    if "unknown step property" in lower:
        return True
    return "extra_forbidden" in lower and "step" in lower


def _issue_from_train_text(
    text: str,
    *,
    agent_id: str,
    model_id: str,
    arm: str,
    event: str,
    raw: str,
) -> IntegrationIssue:
    """Classify one train-failure snippet."""
    if is_session_prose_error(text) or is_session_prose_error(raw):
        return IntegrationIssue(
            code="memory.session_in_prose",
            message=text.strip() or raw.strip(),
            agent_id=agent_id,
            model_id=model_id,
            arm=arm,
            event=event or "mantle.validate_project.project_validation_error",
            report_upstream=True,
            suggested_ask=SESSION_PROSE_ASK,
            raw=raw,
        )
    if is_heading_train_error(text) or is_heading_train_error(raw):
        return IntegrationIssue(
            code="mantle.agent_skills_headings",
            message=text.strip() or raw.strip(),
            agent_id=agent_id,
            model_id=model_id,
            arm=arm,
            event=event or "mantle.validate_project.project_validation_error",
            report_upstream=True,
            suggested_ask=AGENT_SKILLS_HEADING_ASK,
            raw=raw,
        )
    if is_unknown_step_error(text) or is_unknown_step_error(raw):
        return IntegrationIssue(
            code="mantle.unknown_step_property",
            message=text.strip() or raw.strip(),
            agent_id=agent_id,
            model_id=model_id,
            arm=arm,
            event=event or "mantle.validation.skill.failed_to_load",
            report_upstream=True,
            suggested_ask=UNKNOWN_STEP_ASK,
            raw=raw,
        )
    return IntegrationIssue(
        code="rasa.train_failed",
        message=text.strip() or raw.strip() or "rasa train failed",
        agent_id=agent_id,
        model_id=model_id,
        arm=arm,
        event=event,
        report_upstream=True,
        suggested_ask=(
            "rasa train failed on a copied Mantle agent tree. Quote the engine "
            "message in this run's Mantle / Rasa issues section when filing."
        ),
        raw=raw,
    )


def format_arm_label(agent_id: str, model_id: str, arm: str) -> str:
    """Return ``agent/model/arm`` for Layer B logs."""
    return f"{agent_id}/{model_id}/{arm}"


def format_live_eval_start(
    agent_id: str,
    model_id: str,
    arm: str,
    n_scenarios: int,
    repeats: int,
) -> str:
    """Summarize how many live conversations this arm will run."""
    return (
        f"Live eval {format_arm_label(agent_id, model_id, arm)}: "
        f"{n_scenarios} scenarios × {repeats} repeats"
    )


def format_live_scenario_progress(
    agent_id: str,
    model_id: str,
    arm: str,
    scenario_id: str,
    repeat: int,
    repeats: int,
) -> str:
    """Identify one live scenario repeat (1-based) for start and done logs."""
    return (
        f"{format_arm_label(agent_id, model_id, arm)} {scenario_id} "
        f"repeat {repeat + 1}/{repeats}"
    )


def layer_b_eval_hash(config: AppConfig, scenarios_root: Path) -> str:
    """Fingerprint eval knobs, actors, and scenario files for resume invalidation."""
    return text_sha256(
        config.eval.model_dump_json(),
        json.dumps([a.model_dump(mode="json") for a in config.llm.agents], sort_keys=True),
        tree_sha256(scenarios_root),
    )


def _train_agent(
    agent_root: Path,
    *,
    agent_id: str,
    model_id: str,
    arm: str,
    timeout_sync_sec: float | None = None,
    timeout_train_sec: float | None = None,
    log_dir: Path | None = None,
    shared_venv: Path | None = None,
    train_cache_dir: Path | None = None,
) -> tuple[bool, str, list[IntegrationIssue]]:
    """Sync, train, record Mantle validation issues, retry after known workarounds."""
    issues: list[IntegrationIssue] = []
    label = format_arm_label(agent_id, model_id, arm)
    ready, reason = _rasa_ready(agent_root)
    if not ready:
        logger.info("Skipping rasa train for {}: {}", label, reason)
        return False, reason, issues
    fingerprint = _train_fingerprint(agent_root, extra=f"{agent_id}/{arm}")
    cache_models = None
    if train_cache_dir is not None:
        cache_models = train_cache_dir / agent_id / arm / fingerprint / "models"
        if cache_models.is_dir() and any(cache_models.iterdir()):
            logger.info("Train cache hit for {}", label)
            _copy_train_models(cache_models, agent_root)
            return True, "trained from cache", issues
    logger.info("Training {}", label)
    sync_log = (log_dir / f"{agent_id}_{model_id}_{arm}_sync.log") if log_dir else None
    train_log = (log_dir / f"{agent_id}_{model_id}_{arm}_train.log") if log_dir else None
    synced, sync_reason = _try_sync(
        agent_root,
        timeout_sec=timeout_sync_sec,
        log_path=sync_log,
        shared_venv=shared_venv,
    )
    if not synced:
        issues.append(
            IntegrationIssue(
                code="harness.uv_sync",
                message=sync_reason,
                agent_id=agent_id,
                model_id=model_id,
                arm=arm,
                source="uv_sync",
                report_upstream=False,
                suggested_ask="",
                raw=sync_reason,
            )
        )
        return False, sync_reason, issues
    trained, train_reason = _try_rasa_train(
        agent_root,
        timeout_sec=timeout_train_sec,
        log_path=train_log,
        shared_venv=shared_venv,
    )
    if trained:
        if cache_models is not None and (agent_root / "models").is_dir():
            cache_models.parent.mkdir(parents=True, exist_ok=True)
            _copy_train_models(agent_root / "models", cache_models.parent)
        logger.info("Trained {}", label)
        return True, "trained", issues
    issues.extend(
        parse_train_issues(
            train_reason, agent_id=agent_id, model_id=model_id, arm=arm
        )
    )
    return _retry_train_workarounds(
        agent_root,
        issues=issues,
        train_reason=train_reason,
        label=label,
        timeout_train_sec=timeout_train_sec,
        train_log=train_log,
        shared_venv=shared_venv,
        cache_models=cache_models,
        agent_id=agent_id,
        model_id=model_id,
        arm=arm,
    )


_TRAIN_WORKAROUNDS: tuple[tuple[str, str, str], ...] = (
    (
        "memory.session_in_prose",
        "session-prose",
        "rewrote {n} session.* token(s) in instruction prose to @memory.session.*",
    ),
    (
        "mantle.unknown_step_property",
        "unknown-step",
        "stripped {n} unknown ordered_block step key(s)",
    ),
)


def _apply_train_workaround(code: str, agent_root: Path) -> int:
    """Dispatch a train-recovery rewrite so tests can monkeypatch the helpers."""
    if code == "memory.session_in_prose":
        return apply_session_prose_workaround(agent_root)
    if code == "mantle.unknown_step_property":
        return apply_unknown_step_workaround(agent_root)
    return 0


def _retry_train_workarounds(
    agent_root: Path,
    *,
    issues: list[IntegrationIssue],
    train_reason: str,
    label: str,
    timeout_train_sec: float | None,
    train_log: Path | None,
    shared_venv: Path | None,
    cache_models: Path | None,
    agent_id: str,
    model_id: str,
    arm: str,
) -> tuple[bool, str, list[IntegrationIssue]]:
    """Retry ``rasa train`` after each applicable Mantle workaround."""
    tried: set[str] = set()
    current_reason = train_reason
    while True:
        pending = next(
            (
                item
                for item in _TRAIN_WORKAROUNDS
                if item[0] not in tried and any(issue.code == item[0] for issue in issues)
            ),
            None,
        )
        if pending is None:
            return False, current_reason, issues
        code, name, template = pending
        tried.add(code)
        replaced = int(_apply_train_workaround(code, agent_root))
        workaround = template.format(n=replaced)
        for item in issues:
            if item.code == code and not item.workaround_applied:
                item.workaround_applied = workaround
        if replaced == 0:
            for item in issues:
                if item.code == code:
                    item.workaround_succeeded = False
            continue
        trained_again, retry_reason = _try_rasa_train(
            agent_root,
            timeout_sec=timeout_train_sec,
            log_path=train_log,
            shared_venv=shared_venv,
        )
        if trained_again:
            for item in issues:
                if item.code == code:
                    item.workaround_succeeded = True
            if cache_models is not None and (agent_root / "models").is_dir():
                cache_models.parent.mkdir(parents=True, exist_ok=True)
                _copy_train_models(agent_root / "models", cache_models.parent)
            logger.warning(
                "rasa train recovered for {} after {} workaround ({})",
                label,
                name,
                workaround,
            )
            logger.info("Trained {}", label)
            return True, f"trained after {name} workaround", issues
        for item in issues:
            if item.code == code:
                item.workaround_succeeded = False
        issues.extend(
            parse_train_issues(
                retry_reason, agent_id=agent_id, model_id=model_id, arm=arm
            )
        )
        current_reason = retry_reason


def _arm_fail_reason(
    rows: list[TsrRun],
    issues: list[IntegrationIssue],
) -> str | None:
    """Return a short coverage reason for an incomplete Layer B arm."""
    for row in rows:
        if row.skipped and row.skip_reason:
            return str(row.skip_reason)[:500]
    if issues:
        message = issues[0].message or issues[0].code
        return str(message)[:500]
    return None


def _load_observed_fixture(
    run_dir: Path,
    arm: str,
    scenario_id: str,
    repeat: int | None = None,
    *,
    agent_id: str = "rasano",
    model_id: str = "default",
) -> ObservedTrace | None:
    """Load an observation only from the exact agent/model/arm path."""
    names = [f"{scenario_id}.json"]
    if repeat is not None:
        names.insert(0, f"{scenario_id}__r{repeat}.json")
    root = run_dir / "tsr" / "observations" / agent_id / model_id / arm
    for name in names:
        path = root / name
        if not path.is_file():
            continue
        raw = json.loads(path.read_text(encoding="utf-8"))
        observed = ObservedTrace.model_validate(raw)
        return observed.model_copy(update={"source": "fixture", "source_path": str(path)})
    return None


def _save_observation(
    run_dir: Path,
    arm: str,
    spec: dict[str, Any],
    repeat: int,
    observed: ObservedTrace,
    *,
    agent_id: str,
    model_id: str,
) -> None:
    """Persist a live observation and a DeepEval-shaped transcript."""
    scenario_id = str(spec["id"])
    dest = run_dir / "tsr" / "observations" / agent_id / model_id / arm
    dest.mkdir(parents=True, exist_ok=True)
    payload = observed.model_copy(update={"source": "live", "source_path": None})
    (dest / f"{scenario_id}__r{repeat}.json").write_text(
        payload.model_dump_json(indent=2),
        encoding="utf-8",
    )
    transcript = run_dir / "tsr" / "transcripts" / agent_id / model_id / arm
    transcript.mkdir(parents=True, exist_ok=True)
    turns = spec.get("turns") if isinstance(spec.get("turns"), list) else []
    user_text = " | ".join(
        str(turn.get("user") or "") for turn in turns if isinstance(turn, dict)
    )
    (transcript / f"{scenario_id}__r{repeat}.json").write_text(
        json.dumps({"input": user_text, "output": observed.bot_text}, indent=2),
        encoding="utf-8",
    )


def _is_timeout(exc: BaseException) -> bool:
    """True when a live scenario failed because a deadline was hit."""
    text = str(exc).lower()
    return isinstance(exc, TimeoutError) or "timed out" in text or "timeout" in text


def run_arm(
    agent_root: Path,
    arm: str,
    config: AppConfig,
    run_dir: Path,
    *,
    agent_id: str = "rasano",
    model_id: str = "default",
    model: LlmEndpointSettings | None = None,
    existing_rows: list[TsrRun] | None = None,
) -> tuple[list[TsrRun], list[IntegrationIssue]]:
    """Score every scenario × repeat for one agent arm and model."""
    scenarios = load_scenarios(run_dir / "eval" / "scenarios", agent_id=agent_id)
    if not scenarios:
        scenarios = load_scenarios(agent_id=agent_id)
    weights = config.eval.tsr_weights
    repeats = max(1, config.eval.repeats)
    shared_venv = _shared_venv(run_dir, agent_root)
    trained, train_reason, issues = _train_agent(
        agent_root,
        agent_id=agent_id,
        model_id=model_id,
        arm=arm,
        timeout_sync_sec=config.eval.sync_timeout_sec,
        timeout_train_sec=config.eval.train_timeout_sec,
        log_dir=run_dir / "logs",
        shared_venv=shared_venv,
        train_cache_dir=run_dir.parent / ".train-cache",
    )
    arm_label = format_arm_label(agent_id, model_id, arm)
    if not trained:
        logger.warning("rasa train failed for {}: {}", arm_label, train_reason)
    embeddings = config.llm.embeddings if agent_id == "rasano" else None
    if model is not None:
        stamp_runtime_llm(agent_root, model, embeddings)

    server: RasaRestServer | None = None
    live_reason = train_reason
    if trained:
        try:
            server = RasaRestServer(
                agent_root,
                env=_rasa_env(shared_venv),
                startup_timeout_sec=config.eval.rasa_startup_timeout_sec,
                turn_timeout_sec=config.eval.turn_timeout_sec,
                scenario_timeout_sec=config.eval.scenario_timeout_sec,
            )
            server.start()
        except Exception as exc:
            logger.warning("rasa run failed for {}: {}", arm_label, exc)
            live_reason = str(exc)
            if server is not None:
                server.stop()
            server = None
            issues.append(
                IntegrationIssue(
                    code="rasa.run_failed",
                    message=str(exc),
                    agent_id=agent_id,
                    model_id=model_id,
                    arm=arm,
                    source="rasa_run",
                    report_upstream=True,
                    suggested_ask=(
                        "rasa run failed after a successful train. Quote the server "
                        "error from this run's Mantle / Rasa issues section when filing."
                    ),
                    raw=str(exc),
                )
            )

    rows: list[TsrRun] = []
    consecutive_timeouts = 0
    breaker = max(1, config.eval.consecutive_timeout_limit)
    circuit_open = False
    done_ids = {tsr_identity(row) for row in existing_rows or [] if not row.skipped}
    try:
        if server is not None:
            logger.info(
                "{}",
                format_live_eval_start(
                    agent_id, model_id, arm, len(scenarios), repeats
                ),
            )
        for spec in scenarios:
            scenario_id = str(spec["id"])
            skill = str(spec.get("skill") or "") or None
            expect = spec.get("expect") if isinstance(spec.get("expect"), dict) else {}
            for repeat in range(repeats):
                progress = format_live_scenario_progress(
                    agent_id, model_id, arm, scenario_id, repeat, repeats
                )
                progress_key = (
                    f"scenario:{agent_id}/{model_id}/{arm}/{scenario_id}/{repeat}"
                )
                if (
                    agent_id,
                    model_id,
                    arm,
                    scenario_id,
                    repeat,
                ) in done_ids:
                    logger.info("Resume skip {}", progress)
                    progress_mark(
                        progress_key, "layer_b", "complete", message=f"Reused {progress}"
                    )
                    continue
                if circuit_open:
                    rows.append(
                        TsrRun(
                            scenario_id=scenario_id,
                            skill=skill,
                            arm=arm,
                            repeat=repeat,
                            agent_id=agent_id,
                            model_id=model_id,
                            skipped=True,
                            skip_reason=(
                                f"circuit breaker after {breaker} consecutive timeouts"
                            ),
                        )
                    )
                    progress_mark(
                        progress_key,
                        "layer_b",
                        "skipped",
                        message=f"Skipped {progress}",
                        reason="circuit breaker",
                    )
                    continue
                observed: ObservedTrace | None = None
                if server is not None:
                    try:
                        progress_mark(
                            progress_key, "layer_b", "running", message=f"Running {progress}"
                        )
                        logger.info("Live {}", progress)
                        observed = run_scenario_live(server, spec)
                        consecutive_timeouts = 0
                        logger.info(
                            "Done {} latency={:.1f}s",
                            progress,
                            observed.latency_sec or 0.0,
                        )
                        _save_observation(
                            run_dir,
                            arm,
                            spec,
                            repeat,
                            observed,
                            agent_id=agent_id,
                            model_id=model_id,
                        )
                    except Exception as exc:
                        logger.warning("Live scenario {} failed: {}", progress, exc)
                        rows.append(
                            TsrRun(
                                scenario_id=scenario_id,
                                skill=skill,
                                arm=arm,
                                repeat=repeat,
                                agent_id=agent_id,
                                model_id=model_id,
                                skipped=True,
                                skip_reason=str(exc),
                            )
                        )
                        if _is_timeout(exc):
                            consecutive_timeouts += 1
                            if server is not None and not server.healthy():
                                try:
                                    server.restart()
                                except Exception as restart_exc:
                                    logger.warning(
                                        "Rasa restart failed for {}: {}",
                                        arm_label,
                                        restart_exc,
                                    )
                                    server.stop()
                                    server = None
                            if consecutive_timeouts >= breaker:
                                circuit_open = True
                                logger.warning(
                                    "Opening circuit for {} after {} consecutive timeouts",
                                    arm_label,
                                    consecutive_timeouts,
                                )
                                if server is not None:
                                    server.stop()
                                    server = None
                        progress_mark(
                            progress_key,
                            "layer_b",
                            "skipped",
                            message=f"Failed {progress}",
                            reason=str(exc),
                        )
                        continue
                if observed is None:
                    observed = _load_observed_fixture(
                        run_dir,
                        arm,
                        scenario_id,
                        repeat,
                        agent_id=agent_id,
                        model_id=model_id,
                    )
                if observed is not None:
                    rows.append(
                        score_observation(
                            expect,
                            observed,
                            weights,
                            scenario_id=scenario_id,
                            arm=arm,
                            repeat=repeat,
                            skill=skill,
                            agent_id=agent_id,
                            model_id=model_id,
                        )
                    )
                    progress_mark(
                        progress_key, "layer_b", "complete", message=f"Completed {progress}"
                    )
                    continue
                rows.append(
                    TsrRun(
                        scenario_id=scenario_id,
                        skill=skill,
                        arm=arm,
                        repeat=repeat,
                        agent_id=agent_id,
                        model_id=model_id,
                        skipped=True,
                        skip_reason=(
                            live_reason
                            if not trained or server is None
                            else "no live tracker and no exact tsr/observations fixture"
                        ),
                    )
                )
                progress_mark(
                    progress_key,
                    "layer_b",
                    "skipped",
                    message=f"Skipped {progress}",
                    reason=rows[-1].skip_reason,
                )
    finally:
        if server is not None:
            server.stop()
    return rows, issues


def _skipped_actor_rows(
    config: AppConfig,
    run_dir: Path,
    model_id: str,
    reason: str,
) -> list[TsrRun]:
    """Emit skipped TSR rows so a failed actor still appears in coverage."""
    rows: list[TsrRun] = []
    repeats = max(1, config.eval.repeats)
    for agent_id in _LAYER_B_AGENTS:
        scenarios = load_scenarios(run_dir / "eval" / "scenarios", agent_id=agent_id)
        if not scenarios:
            scenarios = load_scenarios(agent_id=agent_id)
        for spec in scenarios:
            scenario_id = str(spec["id"])
            skill = str(spec.get("skill") or "") or None
            for arm in ("native", "improved"):
                for repeat in range(repeats):
                    rows.append(
                        TsrRun(
                            scenario_id=scenario_id,
                            skill=skill,
                            arm=arm,
                            repeat=repeat,
                            agent_id=agent_id,
                            model_id=model_id,
                            skipped=True,
                            skip_reason=reason,
                        )
                    )
    return rows


def _expected_arm_count(config: AppConfig, run_dir: Path, agent_id: str) -> int:
    """How many scenario-repeats one arm should produce."""
    scenarios = load_scenarios(run_dir / "eval" / "scenarios", agent_id=agent_id)
    if not scenarios:
        scenarios = load_scenarios(agent_id=agent_id)
    return max(1, len(scenarios)) * max(1, config.eval.repeats)


def successful_arm_count(
    rows: list[TsrRun],
    *,
    agent_id: str,
    model_id: str,
    arm: str,
) -> int:
    """Count unique, non-skipped scenario repeats for one Layer B arm."""
    return len(
        {
            tsr_identity(row)
            for row in rows
            if row.agent_id == agent_id
            and row.model_id == model_id
            and row.arm == arm
            and not row.skipped
        }
    )


def incomplete_actor_ids(
    config: AppConfig,
    run_dir: Path,
    rows: list[TsrRun],
) -> list[str]:
    """Return configured actors with at least one incomplete evaluation arm."""
    incomplete: list[str] = []
    for model in config.llm.agents:
        model_id = model.path_id()
        for agent_id in _LAYER_B_AGENTS:
            if config.corpora.get(agent_id) is None:
                continue
            expected = _expected_arm_count(config, run_dir, agent_id)
            if any(
                successful_arm_count(
                    rows, agent_id=agent_id, model_id=model_id, arm=arm
                )
                < expected
                for arm in ("native", "improved")
            ):
                incomplete.append(model_id)
                break
    return incomplete


def _coverage_status(
    coverage: dict[str, Any],
    cfg: AppConfig,
    selected_model_ids: set[str] | None = None,
) -> str:
    """Return complete when every configured actor finished without failure."""
    units = coverage.get("units") if isinstance(coverage.get("units"), dict) else {}
    for model in cfg.llm.agents:
        if selected_model_ids is not None and model.path_id() not in selected_model_ids:
            continue
        row = units.get(f"actor:{model.path_id()}")
        if not isinstance(row, dict) or row.get("status") != "complete":
            return "partial"
    return "complete"


def run_agent_eval(
    config: AppConfig | None = None,
    run_dir: Path | None = None,
    fetch: bool = False,
    model_ids: set[str] | None = None,
    preserve_completed: bool = False,
) -> Path:
    """Run Layer B for selected actors, preserving completed scenario repeats.

    Lifecycle invariant:
    1. Outer loop iterates over each LLM actor model.
    2. Local models are spawned once per actor via ensure_local_actor, stopping peer actors.
    3. While the model is active, all scenarios across all agents and arms are prompted.
    4. The model server is cleaned up before transitioning to the next actor or at exit.
    """
    del fetch
    load_dotenv()
    cfg = config or load_config()
    dest = run_dir or latest_run_dir(cfg.runs_root())
    if dest is None:
        dest = make_run_dir("heroes_eval", cfg.runs_root())
    dest.mkdir(parents=True, exist_ok=True)
    sink_id = logger.add(dest / "agent_eval.log", level="INFO")
    _copy_scenarios(dest, cfg)

    if not cfg.llm.agents:
        raise ValueError("config.llm.agents must list at least one agent-core model")

    existing = load_run_payload(dest)
    all_rows: list[TsrRun] = tsr_from_payload(existing)
    all_issues: list[IntegrationIssue] = issues_from_payload(existing)
    coverage = load_coverage(dest)
    eval_hash = layer_b_eval_hash(cfg, dest / "eval" / "scenarios")
    hash_ok = coverage.get("eval_hash") == eval_hash
    if coverage.get("eval_hash") and not hash_ok:
        logger.warning("Layer B eval hash changed; not skipping completed units")
    coverage["eval_hash"] = eval_hash
    interrupted = False
    try:
        for model in cfg.llm.agents:
            model_id = model.path_id()
            if model_ids is not None and model_id not in model_ids:
                continue
            actor_key = f"actor:{model_id}"
            actor_complete = True
            for agent_id in _LAYER_B_AGENTS:
                if cfg.corpora.get(agent_id) is None:
                    continue
                expected = _expected_arm_count(cfg, dest, agent_id)
                if any(
                    successful_arm_count(
                        all_rows,
                        agent_id=agent_id,
                        model_id=model_id,
                        arm=arm,
                    )
                    < expected
                    for arm in ("native", "improved")
                ):
                    actor_complete = False
                    break
            if (
                (hash_ok or preserve_completed)
                and unit_status(coverage, actor_key) == "complete"
                and actor_complete
            ):
                logger.info("Resume skip actor {}", model_id)
                continue
            set_coverage_unit(
                coverage, actor_key, status="running", kind="actor", model_id=model_id
            )
            save_coverage(dest, coverage)
            owned = None
            try:
                owned = ensure_local_actor(
                    model,
                    cfg.llm.agents,
                    timeout_sec=cfg.eval.local_startup_timeout_sec,
                    log_dir=dest / "llama",
                )
            except Exception as exc:
                logger.warning("Skipping actor {}: {}", model_id, exc)
                reason = str(exc)
                all_rows = upsert_tsr(
                    all_rows, _skipped_actor_rows(cfg, dest, model_id, reason)
                )
                all_issues = upsert_issues(
                    all_issues,
                    [
                        IntegrationIssue(
                            code="harness.actor_startup",
                            message=reason,
                            model_id=model_id,
                            source="local_llm",
                            report_upstream=False,
                            suggested_ask="",
                            raw=reason,
                        )
                    ],
                )
                set_coverage_unit(
                    coverage,
                    actor_key,
                    status="failed",
                    kind="actor",
                    reason=reason,
                    model_id=model_id,
                    log_path=str(dest / "llama" / f"{model_id}.log"),
                )
                save_coverage(dest, coverage)
                _flush_layer_b(
                    dest, all_rows, all_issues, interrupted=False, coverage=coverage
                )
                continue
            actor_failed = False
            for agent_id in _LAYER_B_AGENTS:
                entry = cfg.corpora.get(agent_id)
                if entry is None:
                    continue
                src = cfg.resolve(entry.dest)
                if not src.is_dir():
                    logger.warning("Skipping {}: corpus missing at {}", agent_id, src)
                    continue
                for arm in ("native", "improved"):
                    arm_key = f"arm:{agent_id}/{model_id}/{arm}"
                    expected = _expected_arm_count(cfg, dest, agent_id)
                    arm_complete = (
                        successful_arm_count(
                            all_rows,
                            agent_id=agent_id,
                            model_id=model_id,
                            arm=arm,
                        )
                        >= expected
                    )
                    if (
                        (hash_ok or preserve_completed)
                        and unit_status(coverage, arm_key) == "complete"
                        and arm_complete
                    ):
                        logger.info("Resume skip {}", arm_key)
                        continue
                    set_coverage_unit(
                        coverage,
                        arm_key,
                        status="running",
                        kind="arm",
                        model_id=model_id,
                        agent_id=agent_id,
                        arm=arm,
                    )
                    save_coverage(dest, coverage)
                    try:
                        arm_root = prepare_agent_tree(
                            dest, cfg, agent_id=agent_id, model=model, arm=arm
                        )
                        rows, issues = run_arm(
                            arm_root,
                            arm,
                            cfg,
                            dest,
                            agent_id=agent_id,
                            model_id=model_id,
                            model=model,
                            existing_rows=all_rows,
                        )
                    except Exception as exc:
                        logger.exception("Arm {} failed; continuing", arm_key)
                        actor_failed = True
                        set_coverage_unit(
                            coverage,
                            arm_key,
                            status="failed",
                            kind="arm",
                            reason=str(exc),
                            model_id=model_id,
                            agent_id=agent_id,
                            arm=arm,
                        )
                        save_coverage(dest, coverage)
                        continue
                    all_rows = upsert_tsr(all_rows, rows)
                    all_issues = upsert_issues(all_issues, issues)
                    tsr_dir = dest / "tsr" / agent_id / model_id
                    tsr_dir.mkdir(parents=True, exist_ok=True)
                    arm_slice = [
                        row
                        for row in all_rows
                        if row.agent_id == agent_id
                        and row.model_id == model_id
                        and row.arm == arm
                    ]
                    atomic_write_json(
                        tsr_dir / f"{arm}.json",
                        [r.model_dump(mode="json") for r in arm_slice],
                    )
                    completed = successful_arm_count(
                        arm_slice,
                        agent_id=agent_id,
                        model_id=model_id,
                        arm=arm,
                    )
                    set_coverage_unit(
                        coverage,
                        arm_key,
                        status="complete" if completed >= expected else "failed",
                        kind="arm",
                        reason=(
                            None
                            if completed >= expected
                            else _arm_fail_reason(arm_slice, issues)
                        ),
                        model_id=model_id,
                        agent_id=agent_id,
                        arm=arm,
                    )
                    save_coverage(dest, coverage)
                    _flush_layer_b(
                        dest, all_rows, all_issues, interrupted=False, coverage=coverage
                    )
            actor_complete = not actor_failed
            for agent_id in _LAYER_B_AGENTS:
                if cfg.corpora.get(agent_id) is None:
                    continue
                expected = _expected_arm_count(cfg, dest, agent_id)
                if any(
                    successful_arm_count(
                        all_rows,
                        agent_id=agent_id,
                        model_id=model_id,
                        arm=arm,
                    )
                    < expected
                    for arm in ("native", "improved")
                ):
                    actor_complete = False
                    break
            set_coverage_unit(
                coverage,
                actor_key,
                status="complete" if actor_complete else "failed",
                kind="actor",
                model_id=model_id,
                pid=None if owned is None else owned.proc.pid,
                log_path=(
                    None
                    if owned is None or owned.log_path is None
                    else str(owned.log_path)
                ),
            )
            save_coverage(dest, coverage)
    except KeyboardInterrupt:
        interrupted = True
        logger.warning("Layer B interrupted; keeping TSR and integration issues written so far")
        raise
    finally:
        if not interrupted:
            try:
                from rasa_skill_eval.deepeval_judge import run_deepeval

                deepeval_rows = run_deepeval(dest, cfg, all_rows)
                merge_run_payload(
                    dest,
                    {"deepeval": [r.model_dump(mode="json") for r in deepeval_rows]},
                )
            except Exception:
                logger.exception("DeepEval failed after Layer B")
        status = (
            "partial"
            if interrupted
            else _coverage_status(coverage, cfg, selected_model_ids=model_ids)
        )
        _flush_layer_b(
            dest,
            all_rows,
            all_issues,
            interrupted=interrupted,
            coverage=coverage,
            status=status,
        )
        stop_local_actors(cfg.llm.agents)
        logger.remove(sink_id)
        logger.info("Wrote TSR rows to {}", dest / "tsr")
    return dest


def _flush_layer_b(
    run_dir: Path,
    rows: list[TsrRun],
    issues: list[IntegrationIssue],
    *,
    interrupted: bool,
    coverage: dict[str, Any] | None = None,
    status: str | None = None,
) -> None:
    """Merge Layer B rows into ``results.json`` without dropping Layer A keys."""
    meta: dict[str, Any] = {"interrupted": interrupted}
    if status is not None:
        meta["status"] = status
    if coverage is not None:
        meta["coverage"] = coverage
        units = coverage.get("units") if isinstance(coverage.get("units"), dict) else {}
        planned = sorted(
            {
                str(row.get("model_id") or "")
                for row in units.values()
                if isinstance(row, dict) and row.get("kind") == "actor" and row.get("model_id")
            }
        )
        completed = sorted(
            {
                str(row.get("model_id") or "")
                for row in units.values()
                if isinstance(row, dict)
                and row.get("kind") == "actor"
                and row.get("status") == "complete"
                and row.get("model_id")
            }
        )
        failed = sorted(
            {
                str(row.get("model_id") or "")
                for row in units.values()
                if isinstance(row, dict)
                and row.get("kind") == "actor"
                and row.get("status") == "failed"
                and row.get("model_id")
            }
        )
        meta["actors_planned"] = planned
        meta["actors_completed"] = completed
        meta["actors_failed"] = failed
    merge_run_payload(
        run_dir,
        {
            "tsr": [r.model_dump(mode="json") for r in rows],
            "integration_issues": [i.model_dump(mode="json") for i in issues],
            "meta": meta,
        },
    )
