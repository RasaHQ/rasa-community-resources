"""Rebuild stats, plots, and run-local markdown reports from a run folder."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from rasa_skill_eval.config import AppConfig, load_config
from rasa_skill_eval.pipeline import (
    deepeval_from_payload,
    deltas_from_payload,
    inventories_from_payload,
    issues_from_payload,
    load_run_payload,
    merge_run_payload,
    nvidia_from_payload,
    tsr_from_payload,
)
from rasa_skill_eval.plots import write_plots
from rasa_skill_eval.progress import progress_mark
from rasa_skill_eval.report import (
    write_improver_delta,
    write_shareable_report,
)
from rasa_skill_eval.runs import latest_run_dir
from rasa_skill_eval.stats import summarize_run


def finalize_report(run_dir: Path | None = None, config: AppConfig | None = None) -> Path:
    """Write run-local REPORT.md, plots, and stats. Does not overwrite docs/REPORT.md."""
    cfg = config or load_config()
    dest = run_dir or latest_run_dir(cfg.runs_root())
    if dest is None or not dest.is_dir():
        raise FileNotFoundError("No run directory. Run uv run skill-eval first.")
    progress_mark("report:finalize", "finalize", "running", message="Building final report")
    payload = load_run_payload(dest)
    inventories = inventories_from_payload(payload)
    nvidia = nvidia_from_payload(payload)
    deltas = deltas_from_payload(payload)
    tsr = tsr_from_payload(payload)
    deepeval = deepeval_from_payload(payload)
    issues = issues_from_payload(payload)
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    interrupted = bool(meta.get("interrupted"))
    imported_from = str(meta.get("imported_from") or "") or None
    kimi_skipped = bool(meta.get("kimi_skipped"))
    stats = summarize_run(nvidia, deltas, tsr)
    merge_run_payload(dest, {"stats": stats})

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    write_plots(dest / "plots", deltas, tsr, deepeval=deepeval, nvidia=nvidia)

    write_improver_delta(dest / "IMPROVER_DELTA.md", deltas)
    write_shareable_report(
        dest / "REPORT.md",
        cfg,
        inventories,
        nvidia,
        deltas,
        tsr,
        deepeval,
        stats,
        assessed_on=stamp,
        plot_rel="plots",
        integration_issues=issues,
        interrupted=interrupted,
        imported_from=imported_from,
        kimi_skipped=kimi_skipped,
    )
    progress_mark("report:finalize", "finalize", "complete", message="Report ready")
    return dest
