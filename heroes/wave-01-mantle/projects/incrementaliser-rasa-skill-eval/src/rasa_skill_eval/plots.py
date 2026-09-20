"""Matplotlib figures for NVIDIA quality, TSR, and tokens."""

from __future__ import annotations

import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from rasa_skill_eval.models import DeepEvalResult, ImproverDelta, NvidiaSkillResult, TsrRun


def model_size_tier(model_id: str) -> str:
    """Return model size category (e.g. 1-2B, 8B, 30B) for a model identifier."""
    match = re.search(r"(\d+(?:\.\d+)?)\s*b\b", model_id, re.IGNORECASE)
    if match:
        val = float(match.group(1))
        if val <= 4.0:
            return "1–2B"
        if 6.0 <= val <= 14.0:
            return "8B"
        if 20.0 <= val <= 45.0:
            return "30B"
    return "Other"


def write_plots(
    dest: Path,
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult] | None = None,
    nvidia: list[NvidiaSkillResult] | None = None,
) -> list[Path]:
    """Write PNG charts into dest directory and return the list of created file paths."""
    dest.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    quality = dest / "quality_delta.png"
    _bar_pairs(
        quality,
        [d.skill_id for d in deltas],
        [d.baseline_quality for d in deltas],
        [d.improved_quality for d in deltas],
        title="NVIDIA quality on projected skills (not task success)",
        ylabel="Quality 0–100",
    )
    written.append(quality)

    rubric_labels, rubric_base, rubric_imp, rubric_n = _rubric_pairs(nvidia or [])
    rubric_path = dest / "rubric_delta.png"
    _bar_pairs(
        rubric_path,
        rubric_labels,
        rubric_base,
        rubric_imp,
        title=f"NVIDIA rubric on projected skills (n={rubric_n[0]}/{rubric_n[1]})",
        ylabel="Rubric 0–100",
    )
    written.append(rubric_path)

    # 1. Individual models comparison (overall mean per model)
    model_ids = sorted({r.model_id for r in tsr if not r.skipped})
    if model_ids:
        model_native = _mean_by_model(tsr, "native")
        model_improved = _mean_by_model(tsr, "improved")
        by_model_path = dest / "tsr_by_model.png"
        _bar_pairs(
            by_model_path,
            model_ids,
            [model_native.get(m) for m in model_ids],
            [model_improved.get(m) for m in model_ids],
            title="Weighted TSR by individual actor model (baseline vs improved)",
            ylabel="TSR 0–1",
        )
        written.append(by_model_path)

    # 2. Individual models broken down by scenario
    for model_id in model_ids or ["default"]:
        subset = [r for r in tsr if r.model_id == model_id]
        native_w = _mean_by_scenario(subset, "native")
        improved_w = _mean_by_scenario(subset, "improved")
        labels = sorted(set(native_w) | set(improved_w))
        safe = model_id.replace("/", "_")
        tsr_path = dest / f"tsr_weighted_{safe}.png"
        _bar_pairs(
            tsr_path,
            labels,
            [native_w.get(k) for k in labels],
            [improved_w.get(k) for k in labels],
            title=f"Weighted TSR by scenario ({model_id})",
            ylabel="TSR 0–1",
        )
        written.append(tsr_path)

    # 3. Model size tier comparison (1–2B, 8B, 30B)
    tier_order = ["1–2B", "8B", "30B"]
    tier_native = _mean_by_tier(tsr, "native")
    tier_improved = _mean_by_tier(tsr, "improved")
    existing_tiers = [t for t in tier_order if t in tier_native or t in tier_improved]
    other_tiers = sorted(
        (set(tier_native) | set(tier_improved)) - set(tier_order)
    )
    all_tiers = existing_tiers + other_tiers
    if all_tiers:
        tier_path = dest / "tsr_by_model_size.png"
        _bar_pairs(
            tier_path,
            all_tiers,
            [tier_native.get(t) for t in all_tiers],
            [tier_improved.get(t) for t in all_tiers],
            title="Weighted TSR by model size tier (baseline vs improved)",
            ylabel="TSR 0–1",
        )
        written.append(tier_path)

    # 4. Overall average across all models by scenario
    native_w = _mean_by_scenario(tsr, "native")
    improved_w = _mean_by_scenario(tsr, "improved")
    labels = sorted(set(native_w) | set(improved_w))
    tsr_path = dest / "tsr_weighted.png"
    _bar_pairs(
        tsr_path,
        labels,
        [native_w.get(k) for k in labels],
        [improved_w.get(k) for k in labels],
        title="Weighted TSR by scenario (all models)",
        ylabel="TSR 0–1",
    )
    written.append(tsr_path)

    native_tok = _mean_tokens(tsr, "native")
    improved_tok = _mean_tokens(tsr, "improved")
    tok_labels = sorted(set(native_tok) | set(improved_tok))
    if tok_labels:
        tok_path = dest / "tokens_per_task.png"
        _bar_pairs(
            tok_path,
            tok_labels,
            [native_tok.get(k) for k in tok_labels],
            [improved_tok.get(k) for k in tok_labels],
            title="Tokens per task (provider usage when available)",
            ylabel="Tokens",
        )
        written.append(tok_path)

    scatter = dest / "nvidia_vs_tsr.png"
    _scatter_quality_tsr(scatter, deltas, tsr)
    written.append(scatter)
    strict_scatter = dest / "nvidia_vs_tsr_strict.png"
    _scatter_quality_tsr(strict_scatter, deltas, tsr, strict=True)
    written.append(strict_scatter)
    written.extend(_write_deepeval_plots(dest, tsr, deepeval or []))
    return written


def _mean_by_model(rows: list[TsrRun], arm: str) -> dict[str, float]:
    """Calculate mean weighted TSR per model for a specific evaluation arm."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row.arm != arm or row.skipped:
            continue
        buckets.setdefault(row.model_id, []).append(row.weighted)
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _mean_by_tier(rows: list[TsrRun], arm: str) -> dict[str, float]:
    """Calculate mean weighted TSR per size tier (1-2B, 8B, 30B) for an arm."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row.arm != arm or row.skipped:
            continue
        tier = model_size_tier(row.model_id)
        buckets.setdefault(tier, []).append(row.weighted)
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _mean_by_scenario(rows: list[TsrRun], arm: str) -> dict[str, float]:
    """Calculate mean weighted TSR per scenario for one arm."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row.arm != arm or row.skipped:
            continue
        label = f"{row.agent_id}:{row.scenario_id}" if row.agent_id else row.scenario_id
        buckets.setdefault(label, []).append(row.weighted)
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _mean_tokens(rows: list[TsrRun], arm: str) -> dict[str, float]:
    """Calculate mean tokens per scenario for one arm."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row.arm != arm or row.tokens is None:
            continue
        label = f"{row.agent_id}:{row.scenario_id}" if row.agent_id else row.scenario_id
        buckets.setdefault(label, []).append(float(row.tokens))
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _bar_pairs(
    path: Path,
    labels: list[str],
    baseline: list[float | None],
    improved: list[float | None],
    *,
    title: str,
    ylabel: str,
) -> None:
    """Render and save a grouped bar chart of baseline vs improved values."""
    if not labels:
        fig, ax = plt.subplots(figsize=(8, 3))
        ax.text(0.5, 0.5, "No data", ha="center", va="center")
        ax.set_title(title)
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        return
    x = range(len(labels))
    width = 0.38
    bvals = [float("nan") if v is None else v for v in baseline]
    ivals = [float("nan") if v is None else v for v in improved]
    fig, ax = plt.subplots(figsize=(max(8, len(labels) * 0.7), 4.5))
    ax.bar([i - width / 2 for i in x], bvals, width, label="baseline")
    ax.bar([i + width / 2 for i in x], ivals, width, label="improved")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=40, ha="right")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


def _norm_skill(name: str) -> str:
    """Normalize skill name across agent directories and scenario fields."""
    return name.split("/")[-1].split("#")[0].replace("-", "_").strip().lower()


def _mean_tsr_by_skill(
    rows: list[TsrRun], arm: str, *, strict: bool = False
) -> dict[str, float]:
    """Calculate mean weighted or strict TSR per skill for one arm."""
    buckets: dict[str, list[float]] = {}
    for row in rows:
        if row.arm != arm or row.skipped:
            continue
        key = _norm_skill(row.skill or row.scenario_id)
        value = float(row.strict) if strict else row.weighted
        buckets.setdefault(key, []).append(value)
    return {k: sum(v) / len(v) for k, v in buckets.items() if v}


def _scatter_quality_tsr(
    path: Path,
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    *,
    strict: bool = False,
) -> None:
    """Render NVIDIA quality delta against weighted or strict TSR delta."""
    fig, ax = plt.subplots(figsize=(9, 7))
    nvidia_d: dict[str, float] = {}
    for delta in deltas:
        if delta.baseline_quality is None or delta.improved_quality is None:
            continue
        nvidia_d[_norm_skill(delta.skill_id)] = (
            delta.improved_quality - delta.baseline_quality
        )
    native = _mean_tsr_by_skill(tsr, "native", strict=strict)
    improved = _mean_tsr_by_skill(tsr, "improved", strict=strict)
    keys = sorted(set(nvidia_d) & set(native) & set(improved))
    if not keys:
        ax.text(0.5, 0.5, "No paired NVIDIA Δ / TSR Δ yet", ha="center", va="center")
        metric_name = "strict TSR" if strict else "weighted TSR"
        ax.set_title(f"Quality lift vs {metric_name} lift (paired by skill)")
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        return

    x_vals = [nvidia_d[k] for k in keys]
    y_vals = [improved[k] - native[k] for k in keys]

    min_x = min(min(x_vals), -2.0) - 2.0
    max_x = max(max(x_vals), 5.0) + 3.0
    min_y = min(min(y_vals), -0.2) - 0.08
    max_y = max(max(y_vals), 0.3) + 0.08

    ax.set_xlim(min_x, max_x)
    ax.set_ylim(min_y, max_y)

    # 1. Shaded zones: Better spot (upper half y > 0) green, lower half red
    ax.axhspan(0, max_y, facecolor="#e8f5e9", alpha=0.55, zorder=0)
    ax.axhspan(min_y, 0, facecolor="#ffebee", alpha=0.55, zorder=0)

    # 2. Quadrant divider lines
    ax.axhline(0, color="#2e7d32", linestyle="--", linewidth=1.5, alpha=0.8, zorder=1)
    ax.axvline(0, color="#78909c", linestyle="--", linewidth=1.2, alpha=0.7, zorder=1)

    # 3. "Better Spot" & "Regression" demarcation labels
    ax.text(
        max_x - 0.3,
        0.015,
        "▲ BETTER SPOT (TSR Lift > 0: More Tasks Completed)",
        color="#1b5e20",
        fontsize=8.5,
        fontweight="bold",
        ha="right",
        va="bottom",
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": "#c8e6c9",
            "edgecolor": "#81c784",
            "alpha": 0.9,
        },
        zorder=2,
    )
    ax.text(
        max_x - 0.3,
        -0.015,
        "▼ REGRESSION / NO GAIN (TSR Lift ≤ 0: Tasks Stagnated or Degraded)",
        color="#b71c1c",
        fontsize=8.5,
        fontweight="bold",
        ha="right",
        va="top",
        bbox={
            "boxstyle": "round,pad=0.25",
            "facecolor": "#ffcdd2",
            "edgecolor": "#e57373",
            "alpha": 0.9,
        },
        zorder=2,
    )

    # 4. Corner quadrant summary
    ax.text(
        min_x + 0.4,
        max_y - 0.02,
        "Top-Right: WIN-WIN ZONE\n(Quality ↑ and TSR ↑)",
        color="#1b5e20",
        fontsize=8.5,
        fontweight="bold",
        ha="left",
        va="top",
        zorder=2,
    )

    # 5. Scatter points
    colors = ["#2e7d32" if y > 0 else "#c62828" for y in y_vals]
    ax.scatter(
        x_vals,
        y_vals,
        c=colors,
        s=90,
        edgecolors="#1a237e",
        linewidth=1.2,
        zorder=4,
    )

    # 6. Point annotations with skill names and exact numbers
    points = sorted(
        zip(keys, x_vals, y_vals, strict=True),
        key=lambda p: p[2],
    )
    for idx, (skill_name, x, y) in enumerate(points):
        # Alternate left/right and up/down to prevent overlap on stacked points
        if idx % 2 == 0:
            offset_x = 16
            offset_y = 12
            ha_align = "left"
        else:
            offset_x = -16
            offset_y = -12
            ha_align = "right"
        sign_x = "+" if x > 0 else ""
        sign_y = "+" if y > 0 else ""
        label = f"{skill_name}\n({sign_x}{x:.1f} Q, {sign_y}{y:.2f} TSR)"
        ax.annotate(
            label,
            xy=(x, y),
            xytext=(offset_x, offset_y),
            textcoords="offset points",
            fontsize=8,
            fontweight="bold",
            color="#212121",
            ha=ha_align,
            va="center",
            bbox={
                "boxstyle": "round,pad=0.25",
                "facecolor": "#ffffff",
                "edgecolor": "#b0bec5",
                "alpha": 0.92,
            },
            arrowprops={
                "arrowstyle": "->",
                "color": "#78909c",
                "lw": 0.9,
            },
            zorder=5,
        )

    ax.set_xlabel(
        "NVIDIA Quality Lift Δ (-100 to +100 static authoring hygiene score lift)",
        fontsize=9.5,
        fontweight="bold",
    )
    tsr_kind = "Strict" if strict else "Weighted"
    ax.set_ylabel(
        f"{tsr_kind} TSR Lift Δ (-1.0 to +1.0 live task completion lift)",
        fontsize=9.5,
        fontweight="bold",
    )
    ax.set_title(
        f"NVIDIA Quality Lift vs Live {tsr_kind} Task Success Rate (TSR) Lift\n"
        "(Paired by Skill Across Evaluated Models)",
        fontsize=10.5,
        fontweight="bold",
        pad=10,
    )
    ax.grid(True, linestyle=":", alpha=0.5, color="#b0bec5", zorder=1)

    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)


_DEEPEVAL_METRICS = (
    ("task_completion", "task completion"),
    ("answer_relevancy", "answer relevancy"),
    ("tool_correctness", "tool correctness"),
    ("g_eval_tool_correctness", "GEval tool correctness"),
)


def _coverage_n(values: list[float], expected: int) -> str:
    """Format scored/expected coverage for a plot title."""
    return f"n={len(values)}/{expected}"


def _planned_identities(tsr: list[TsrRun]) -> set[tuple[str, str, str, str, int]]:
    """Unique non-skipped Layer B identities that DeepEval should cover."""
    return {
        (row.agent_id, row.model_id, row.arm, row.scenario_id, int(row.repeat))
        for row in tsr
        if not row.skipped
    }


def _planned_deepeval_n(tsr: list[TsrRun]) -> int:
    """Count planned DeepEval identities from TSR, or 0 when TSR is empty."""
    return len(_planned_identities(tsr))


def _tsr_model_ids(tsr: list[TsrRun]) -> list[str]:
    """Actor ids present on successful TSR rows."""
    return sorted({row.model_id for row in tsr if not row.skipped and row.model_id})


def _tsr_scenario_labels(tsr: list[TsrRun]) -> list[str]:
    """``agent:scenario`` labels for every successful TSR row."""
    return sorted(
        {
            f"{row.agent_id}:{row.scenario_id}" if row.agent_id else row.scenario_id
            for row in tsr
            if not row.skipped
        }
    )


def _rubric_pairs(
    nvidia: list[NvidiaSkillResult],
) -> tuple[list[str], list[float | None], list[float | None], tuple[int, int]]:
    """Pair baseline vs improved rubric scores by skill id, including hollow rows."""
    baseline: dict[str, float] = {}
    improved: dict[str, float] = {}
    labels: set[str] = set()
    expected = 0
    scored = 0
    for item in nvidia:
        if item.command != "rubric-eval":
            continue
        expected += 1
        skill = item.skill_id.replace("#improved", "")
        labels.add(skill)
        if item.skipped or item.rubric_score is None:
            continue
        scored += 1
        if "#improved" in item.skill_id:
            improved[skill] = item.rubric_score
        else:
            baseline[skill] = item.rubric_score
    ordered = sorted(labels)
    return (
        ordered,
        [baseline.get(label) for label in ordered],
        [improved.get(label) for label in ordered],
        (scored, expected),
    )


def _deepeval_scored(
    rows: list[DeepEvalResult],
    metric: str,
    arm: str,
) -> list[DeepEvalResult]:
    """Return non-skipped scored rows for one metric and arm."""
    return [
        row
        for row in rows
        if row.metric == metric
        and row.arm == arm
        and not row.skipped
        and row.score is not None
    ]


def _mean_deepeval_by_model(
    rows: list[DeepEvalResult], metric: str, arm: str
) -> dict[str, float]:
    """Mean DeepEval score per actor model."""
    buckets: dict[str, list[float]] = {}
    for row in _deepeval_scored(rows, metric, arm):
        buckets.setdefault(row.model_id, []).append(float(row.score or 0.0))
    return {key: sum(vals) / len(vals) for key, vals in buckets.items() if vals}


def _mean_deepeval_by_scenario(
    rows: list[DeepEvalResult], metric: str, arm: str
) -> dict[str, float]:
    """Mean DeepEval score per agent:scenario."""
    buckets: dict[str, list[float]] = {}
    for row in _deepeval_scored(rows, metric, arm):
        label = f"{row.agent_id}:{row.scenario_id}" if row.agent_id else row.scenario_id
        buckets.setdefault(label, []).append(float(row.score or 0.0))
    return {key: sum(vals) / len(vals) for key, vals in buckets.items() if vals}


def _mean_deepeval_by_tier(
    rows: list[DeepEvalResult], metric: str, arm: str
) -> dict[str, float]:
    """Mean DeepEval score per model-size tier."""
    buckets: dict[str, list[float]] = {}
    for row in _deepeval_scored(rows, metric, arm):
        buckets.setdefault(model_size_tier(row.model_id), []).append(float(row.score or 0.0))
    return {key: sum(vals) / len(vals) for key, vals in buckets.items() if vals}


def _deepeval_expected(tsr: list[TsrRun], rows: list[DeepEvalResult], metric: str) -> int:
    """Count planned identities, falling back to attempted DeepEval rows."""
    planned = _planned_deepeval_n(tsr)
    if planned:
        return planned
    identities = {
        (row.agent_id, row.model_id, row.arm, row.scenario_id, row.repeat)
        for row in rows
        if row.metric == metric and row.scenario_id != "*"
    }
    return len(identities)


def _write_deepeval_plots(
    dest: Path,
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
) -> list[Path]:
    """Write native vs improved DeepEval comparison charts."""
    written: list[Path] = []
    metric_native: list[float | None] = []
    metric_improved: list[float | None] = []
    metric_labels: list[str] = []
    for metric, title in _DEEPEVAL_METRICS:
        native_vals = [
            float(row.score or 0.0) for row in _deepeval_scored(deepeval, metric, "native")
        ]
        improved_vals = [
            float(row.score or 0.0) for row in _deepeval_scored(deepeval, metric, "improved")
        ]
        expected = _deepeval_expected(tsr, deepeval, metric)
        metric_labels.append(f"{title}\n{_coverage_n(native_vals + improved_vals, expected)}")
        metric_native.append(sum(native_vals) / len(native_vals) if native_vals else None)
        metric_improved.append(
            sum(improved_vals) / len(improved_vals) if improved_vals else None
        )

        native_m = _mean_deepeval_by_model(deepeval, metric, "native")
        improved_m = _mean_deepeval_by_model(deepeval, metric, "improved")
        model_ids = _tsr_model_ids(tsr) or sorted(set(native_m) | set(improved_m))
        by_model = dest / f"deepeval_{metric}_by_model.png"
        _bar_pairs(
            by_model,
            model_ids,
            [native_m.get(model_id) for model_id in model_ids],
            [improved_m.get(model_id) for model_id in model_ids],
            title=(
                f"DeepEval {title} by actor "
                f"(n={len(native_vals) + len(improved_vals)}/{expected})"
            ),
            ylabel="Score 0–1",
        )
        written.append(by_model)

        native_s = _mean_deepeval_by_scenario(deepeval, metric, "native")
        improved_s = _mean_deepeval_by_scenario(deepeval, metric, "improved")
        labels = _tsr_scenario_labels(tsr) or sorted(set(native_s) | set(improved_s))
        by_scenario = dest / f"deepeval_{metric}_by_scenario.png"
        _bar_pairs(
            by_scenario,
            labels,
            [native_s.get(label) for label in labels],
            [improved_s.get(label) for label in labels],
            title=(
                f"DeepEval {title} by scenario "
                f"(n={len(native_vals) + len(improved_vals)}/{expected})"
            ),
            ylabel="Score 0–1",
        )
        written.append(by_scenario)

    scored_n = 0
    expected_n = 0
    for metric, _title in _DEEPEVAL_METRICS:
        scored_n += len(_deepeval_scored(deepeval, metric, "native")) + len(
            _deepeval_scored(deepeval, metric, "improved")
        )
        expected_n += _deepeval_expected(tsr, deepeval, metric)
    overall = dest / "deepeval_by_metric.png"
    _bar_pairs(
        overall,
        metric_labels,
        metric_native,
        metric_improved,
        title=(
            "DeepEval native vs improved "
            f"(n={scored_n}/{expected_n} across metrics)"
        ),
        ylabel="Score 0–1",
    )
    written.append(overall)

    native_task = _mean_deepeval_by_model(deepeval, "task_completion", "native")
    improved_task = _mean_deepeval_by_model(deepeval, "task_completion", "improved")
    model_ids = _tsr_model_ids(tsr) or sorted(set(native_task) | set(improved_task))
    by_model = dest / "deepeval_by_model.png"
    expected_task = _deepeval_expected(tsr, deepeval, "task_completion")
    scored_task = len(_deepeval_scored(deepeval, "task_completion", "native")) + len(
        _deepeval_scored(deepeval, "task_completion", "improved")
    )
    _bar_pairs(
        by_model,
        model_ids,
        [native_task.get(model_id) for model_id in model_ids],
        [improved_task.get(model_id) for model_id in model_ids],
        title=f"DeepEval task completion by actor (n={scored_task}/{expected_task})",
        ylabel="Score 0–1",
    )
    written.append(by_model)

    native_scen = _mean_deepeval_by_scenario(deepeval, "task_completion", "native")
    improved_scen = _mean_deepeval_by_scenario(deepeval, "task_completion", "improved")
    scen_labels = _tsr_scenario_labels(tsr) or sorted(set(native_scen) | set(improved_scen))
    by_scenario = dest / "deepeval_by_scenario.png"
    _bar_pairs(
        by_scenario,
        scen_labels,
        [native_scen.get(label) for label in scen_labels],
        [improved_scen.get(label) for label in scen_labels],
        title=f"DeepEval task completion by scenario (n={scored_task}/{expected_task})",
        ylabel="Score 0–1",
    )
    written.append(by_scenario)

    native_tier = _mean_deepeval_by_tier(deepeval, "task_completion", "native")
    improved_tier = _mean_deepeval_by_tier(deepeval, "task_completion", "improved")
    tier_order = ["1–2B", "8B", "30B"]
    existing_tiers = [tier for tier in tier_order if tier in native_tier or tier in improved_tier]
    other_tiers = sorted((set(native_tier) | set(improved_tier)) - set(tier_order))
    all_tiers = existing_tiers + other_tiers
    by_size = dest / "deepeval_by_model_size.png"
    _bar_pairs(
        by_size,
        all_tiers,
        [native_tier.get(tier) for tier in all_tiers],
        [improved_tier.get(tier) for tier in all_tiers],
        title=f"DeepEval task completion by model size (n={scored_task}/{expected_task})",
        ylabel="Score 0–1",
    )
    written.append(by_size)

    scatter = dest / "deepeval_vs_tsr.png"
    _scatter_deepeval_tsr(scatter, tsr, deepeval)
    written.append(scatter)
    return written


def _scatter_deepeval_tsr(
    path: Path,
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
) -> None:
    """Plot Δ task_completion against Δ weighted TSR, paired by scenario."""
    fig, ax = plt.subplots(figsize=(9, 7))
    native_tsr = _mean_by_scenario(tsr, "native")
    improved_tsr = _mean_by_scenario(tsr, "improved")
    native_de = _mean_deepeval_by_scenario(deepeval, "task_completion", "native")
    improved_de = _mean_deepeval_by_scenario(deepeval, "task_completion", "improved")
    keys = sorted(set(native_tsr) & set(improved_tsr) & set(native_de) & set(improved_de))
    if not keys:
        ax.text(0.5, 0.5, "No paired DeepEval Δ / TSR Δ yet", ha="center", va="center")
        ax.set_title("DeepEval task completion lift vs weighted TSR lift")
        fig.tight_layout()
        fig.savefig(path, dpi=140)
        plt.close(fig)
        return
    x_vals = [improved_de[key] - native_de[key] for key in keys]
    y_vals = [improved_tsr[key] - native_tsr[key] for key in keys]
    ax.axhline(0, color="#78909c", linestyle="--", linewidth=1.2)
    ax.axvline(0, color="#78909c", linestyle="--", linewidth=1.2)
    colors = ["#2e7d32" if y_val > 0 else "#c62828" for y_val in y_vals]
    ax.scatter(x_vals, y_vals, c=colors, s=90, edgecolors="#1a237e", linewidth=1.2)
    for key, x_val, y_val in zip(keys, x_vals, y_vals, strict=True):
        ax.annotate(
            key, (x_val, y_val), fontsize=7, xytext=(6, 6), textcoords="offset points"
        )
    ax.set_xlabel("DeepEval task completion lift (improved − native)")
    ax.set_ylabel("Weighted TSR lift (improved − native)")
    ax.set_title("DeepEval task completion lift vs live TSR lift (paired by scenario)")
    ax.grid(True, linestyle=":", alpha=0.5)
    fig.tight_layout()
    fig.savefig(path, dpi=140)
    plt.close(fig)
