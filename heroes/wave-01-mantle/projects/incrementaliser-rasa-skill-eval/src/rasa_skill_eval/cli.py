"""Console scripts: fetch-corpus, skill-eval, agent-eval, report, eval-all, run-all2."""

from __future__ import annotations

import argparse
import os
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger
from rich.console import Console
from rich.table import Table

from rasa_skill_eval.agent_eval import incomplete_actor_ids, run_agent_eval
from rasa_skill_eval.config import AppConfig, load_config
from rasa_skill_eval.corpus import fetch_all
from rasa_skill_eval.deepeval_judge import run_deepeval
from rasa_skill_eval.finalize import finalize_report
from rasa_skill_eval.pipeline import (
    discover_first_skill,
    load_run_payload,
    merge_run_payload,
    run_pipeline,
    seed_imported_layer_a,
    tsr_from_payload,
)
from rasa_skill_eval.progress import (
    ProgressManager,
    reset_current_progress,
    set_current_progress,
)
from rasa_skill_eval.runs import clone_run_dir, latest_run_dir, make_run_dir
from rasa_skill_eval.tracking import MlflowTracker, WandbTracker
from rasa_skill_eval.ui import TerminalProgressUI


def fetch_corpus_main() -> None:
    """Download pinned corpora into ``corpus/`` and vendor improver skills."""
    config = load_config()
    shas = fetch_all(config)
    for name, sha in shas.items():
        print(f"{name}: {sha}")


def _common_parser(description: str) -> argparse.ArgumentParser:
    """Shared flags for eval commands."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not clone corpora even if Rasano is missing.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Reuse this run folder; skip completed Layer A skills and Layer B arms.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip Rasano TSR (eval-all only).",
    )
    parser.add_argument(
        "--reimprove",
        action="store_true",
        help="Ignore the improver cache and rewrite projected skills again.",
    )
    parser.add_argument(
        "--retry-degraded",
        action="store_true",
        help="Retry improver LLM rewriting only on skills marked degraded.",
    )
    parser.add_argument(
        "--no-progress",
        action="store_true",
        help="Disable interactive Rich progress bars; run-local logs are still written.",
    )
    parser.add_argument(
        "--tracking-uri",
        default=None,
        help="Optional MLflow tracking URI (also read from MLFLOW_TRACKING_URI).",
    )
    return parser


@contextmanager
def _progress_session(
    run_dir: Path,
    cfg: AppConfig,
    args: argparse.Namespace,
    *,
    source_run: str | None = None,
) -> Iterator[ProgressManager]:
    """Activate durable, terminal, and optional MLflow/W&B progress observers."""
    agents = cfg.llm.agents
    repeats = cfg.eval.repeats
    ui = TerminalProgressUI(enabled=not bool(getattr(args, "no_progress", False)))
    parameters = {
        "agents": ",".join(model.path_id() for model in agents),
        "repeats": repeats,
    }
    mlflow_tracker = MlflowTracker(
        run_dir,
        tracking_uri=(
            getattr(args, "tracking_uri", None)
            or os.getenv("MLFLOW_TRACKING_URI")
            or cfg.tracking.mlflow.tracking_uri
        ),
        source_run=source_run,
        parameters=parameters,
    )
    wandb_tracker = WandbTracker(run_dir, parameters=parameters)
    manager = ProgressManager(run_dir, observers=[ui, mlflow_tracker, wandb_tracker])
    manager.seed_from_run(cfg)
    token = set_current_progress(manager)
    try:
        yield manager
    finally:
        manager.close()
        reset_current_progress(token)


def skill_eval_main() -> None:
    """Inventory, convert to Agent Skills, improve, NVIDIA T1–T3."""
    parser = _common_parser("Project Mantle skills and score NVIDIA tiers.")
    args = parser.parse_args()
    cfg = load_config()
    run_dir = args.run_dir or make_run_dir("heroes_eval", cfg.runs_root())
    with _progress_session(run_dir, cfg, args):
        run_pipeline(
            config=cfg,
            fetch=not args.no_fetch,
            run_dir=run_dir,
            reimprove=args.reimprove,
            retry_degraded=args.retry_degraded,
        )
    logger.info("Done: {}", run_dir)


def agent_eval_main() -> None:
    """Native vs improved Rasano, weighted TSR + DeepEval."""
    parser = _common_parser("Run Mantle TSR on native vs reverse-merged skills.")
    args = parser.parse_args()
    cfg = load_config()
    run_dir = args.run_dir or make_run_dir("heroes_eval", cfg.runs_root())
    with _progress_session(run_dir, cfg, args):
        run_agent_eval(config=cfg, run_dir=run_dir, fetch=not args.no_fetch)
    logger.info("Done: {}", run_dir)


def report_main() -> None:
    """Stats, plots, and run-local REPORT.md from the latest (or given) run."""
    parser = _common_parser("Write the shareable report from a run folder.")
    args = parser.parse_args()
    cfg = load_config()
    dest = args.run_dir or latest_run_dir(cfg.runs_root())
    if dest is None:
        raise FileNotFoundError("No run directory. Run uv run skill-eval first.")
    with _progress_session(dest, cfg, args):
        finalize_report(run_dir=dest, config=cfg)
    logger.info("Wrote report in {}", dest)


def eval_all_main() -> None:
    """One dated folder: skill-eval, then agent-eval, then report."""
    parser = _common_parser("Full pipeline into one runs/heroes_eval_* folder.")
    args = parser.parse_args()
    cfg = load_config()
    load_dotenv()
    if not os.getenv("NVIDIA_API_KEY", "").strip():
        logger.warning(
            "NVIDIA_API_KEY is unset; NIM improver, judge, embeddings, and SkillEvaluator will skip"
        )
    if not os.getenv("RASA_LICENSE", "").strip():
        logger.warning("RASA_LICENSE is unset; rasa train will skip and Layer B TSR will be n/a")
    run_dir = args.run_dir or make_run_dir("heroes_eval", cfg.runs_root())
    with _progress_session(run_dir, cfg, args):
        try:
            run_pipeline(
                config=cfg,
                fetch=not args.no_fetch,
                run_dir=run_dir,
                reimprove=args.reimprove,
                retry_degraded=args.retry_degraded,
            )
            if not args.skip_agent:
                run_agent_eval(config=cfg, run_dir=run_dir, fetch=False)
        except KeyboardInterrupt:
            logger.warning("eval-all interrupted; writing partial report from disk")
            raise
        except Exception:
            logger.exception("eval-all failed; writing partial report from disk")
            raise
        finally:
            try:
                finalize_report(run_dir=run_dir, config=cfg)
            except Exception:
                logger.exception("finalize_report failed after eval-all stop")
    logger.info("Done: {}", run_dir or latest_run_dir())


def resume_missing_main() -> None:
    """Clone one run, retry incomplete evaluations, and rebuild its reports."""
    parser = argparse.ArgumentParser(
        description="Clone an evaluation run and complete only missing work."
    )
    parser.add_argument(
        "--source-run",
        type=Path,
        required=True,
        help="Existing run to preserve and clone before resuming.",
    )
    parser.add_argument(
        "--reimprove",
        action="store_true",
        help="Ignore the improver cache and force LLM rewriting of all skills.",
    )
    parser.add_argument(
        "--retry-degraded",
        action="store_true",
        help="Explicitly retry improver LLM rewriting only on skills marked degraded.",
    )
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--tracking-uri", default=None)
    args = parser.parse_args()
    cfg = load_config()
    source = args.source_run.resolve()
    dest = clone_run_dir(source, cfg.runs_root())
    logger.info("Cloned immutable source {} to {}", source, dest)

    with _progress_session(dest, cfg, args, source_run=str(source)):
        run_pipeline(
            config=cfg,
            fetch=False,
            run_dir=dest,
            reimprove=args.reimprove,
            retry_degraded=args.retry_degraded,
            retry_incomplete=True,
            preserve_projections=not args.reimprove,
        )
        rows = tsr_from_payload(load_run_payload(dest))
        missing_models = set(incomplete_actor_ids(cfg, dest, rows))
        if missing_models:
            logger.info("Incomplete Layer B actors: {}", ", ".join(sorted(missing_models)))
            run_agent_eval(
                config=cfg,
                run_dir=dest,
                fetch=False,
                model_ids=missing_models,
                preserve_completed=True,
            )
        else:
            logger.info("Layer B is already complete")
            deepeval_rows = run_deepeval(dest, cfg, rows)
            merge_run_payload(
                dest,
                {"deepeval": [row.model_dump(mode="json") for row in deepeval_rows]},
            )
        finalize_report(run_dir=dest, config=cfg)
    logger.info("Done: {}", dest)


def test_pipeline_main() -> None:
    """Run full pipeline smoke test on one globally selected skill and one agent model."""
    parser = argparse.ArgumentParser(
        description="Run end-to-end evaluation testing exactly one skill and one core model."
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not clone corpora even if Rasano is missing.",
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help="Custom run directory; defaults to a dated test_pipeline_* run directory.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip Layer B agent eval.",
    )
    parser.add_argument(
        "--reimprove",
        action="store_true",
        help="Ignore the improver cache and rewrite projected skill again.",
    )
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--tracking-uri", default=None)
    args = parser.parse_args()

    cfg = load_config()
    load_dotenv()

    # Deterministically select one agent core model
    if not cfg.llm.agents:
        raise ValueError("config.llm.agents must list at least one agent-core model")
    selected_model = cfg.llm.agents[0]
    test_cfg = cfg.model_copy(
        update={
            "llm": cfg.llm.model_copy(
                update={"agents": [selected_model]}
            )
        }
    )

    # Deterministically select one skill globally
    selected_skill = discover_first_skill(test_cfg)
    logger.info(
        "test-pipeline active: model={} skill={}",
        selected_model.path_id(),
        selected_skill or "all",
    )

    run_dir = args.run_dir or make_run_dir("test_pipeline", test_cfg.runs_root())
    with _progress_session(run_dir, test_cfg, args):
        try:
            run_pipeline(
                config=test_cfg,
                fetch=not args.no_fetch,
                run_dir=run_dir,
                reimprove=args.reimprove,
                only_skill_key=selected_skill,
            )
            if not args.skip_agent:
                run_agent_eval(
                    config=test_cfg,
                    run_dir=run_dir,
                    fetch=False,
                    model_ids={selected_model.path_id()},
                )
        except KeyboardInterrupt:
            logger.warning("test-pipeline interrupted; writing partial report")
            raise
        except Exception:
            logger.exception("test-pipeline failed; writing partial report")
            raise
        finally:
            try:
                finalize_report(run_dir=run_dir, config=test_cfg)
            except Exception:
                logger.exception("finalize_report failed after test-pipeline stop")
    logger.info("Done test-pipeline: {}", run_dir)


def run_all2_main() -> None:
    """Rerun Layer A scoring and Linux Layer B from donated projected/improved packages.

    Default source is ``runs/zfiles``. Kimi is never called. Windows agent trees
    and coverage are not copied.
    """
    parser = argparse.ArgumentParser(
        description="Seed Layer A from a donated run and rerun NVIDIA plus Linux Layer B."
    )
    parser.add_argument(
        "--source-run",
        type=Path,
        default=Path("runs/zfiles"),
        help="Donated run with projected/ and improved/ (default: runs/zfiles).",
    )
    parser.add_argument(
        "--no-fetch",
        action="store_true",
        help="Do not clone corpora even if Rasano is missing.",
    )
    parser.add_argument(
        "--skip-agent",
        action="store_true",
        help="Skip Layer B agent eval.",
    )
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--tracking-uri", default=None)
    args = parser.parse_args()
    cfg = load_config()
    load_dotenv()
    source = args.source_run
    if not source.is_absolute():
        source = cfg.resolve(source.as_posix())
    run_dir = make_run_dir("run_all2", cfg.runs_root())
    logger.info("Seeding Layer A from {} into {}", source, run_dir)
    seed_imported_layer_a(source, run_dir)
    with _progress_session(run_dir, cfg, args, source_run=str(source)):
        try:
            run_pipeline(
                config=cfg,
                fetch=not args.no_fetch,
                run_dir=run_dir,
                reimprove=False,
                skip_improver=True,
                preserve_projections=True,
            )
            if not args.skip_agent:
                run_agent_eval(config=cfg, run_dir=run_dir, fetch=False)
        except KeyboardInterrupt:
            logger.warning("run-all2 interrupted; writing partial report from disk")
            raise
        except Exception:
            logger.exception("run-all2 failed; writing partial report from disk")
            raise
        finally:
            try:
                finalize_report(run_dir=run_dir, config=cfg)
            except Exception:
                logger.exception("finalize_report failed after run-all2 stop")
    logger.info("Done run-all2: {}", run_dir)


def progress_main() -> None:
    """Display a run progress manifest once or refresh it until interrupted."""
    parser = argparse.ArgumentParser(description="Show progress for an evaluation run.")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    console = Console()
    try:
        while True:
            raw = load_run_payload(args.run_dir)
            progress_path = args.run_dir / "progress.json"
            if progress_path.is_file():
                import json

                raw = json.loads(progress_path.read_text(encoding="utf-8"))
            table = Table(title=f"Progress: {args.run_dir.name}")
            table.add_column("Phase")
            table.add_column("Done", justify="right")
            table.add_column("Total", justify="right")
            table.add_column("Percent", justify="right")
            for phase in ("layer_a", "layer_b", "deepeval", "finalize"):
                summary = raw.get(phase) or {}
                table.add_row(
                    phase,
                    str(summary.get("done", 0)),
                    str(summary.get("total", 0)),
                    f"{float(summary.get('pct', 0)):.1f}%",
                )
            console.clear()
            console.print(table)
            if not args.watch:
                break
            time.sleep(2)
    except KeyboardInterrupt:
        return
