"""Confidence intervals and paired tests for NVIDIA and TSR deltas."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
from scipy import stats

from rasa_skill_eval.models import ImproverDelta, NvidiaSkillResult, TsrRun


def _mean_ci(values: list[float]) -> dict[str, float | None]:
    """Normal-approx 95% CI on the mean. Tiny n stays honest."""
    if not values:
        return {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    if arr.size < 2:
        return {"n": int(arr.size), "mean": mean, "ci_low": mean, "ci_high": mean}
    sem = float(stats.sem(arr))
    interval = stats.t.interval(0.95, arr.size - 1, loc=mean, scale=sem)
    return {
        "n": int(arr.size),
        "mean": mean,
        "ci_low": float(interval[0]),
        "ci_high": float(interval[1]),
    }


def paired_delta_test(baseline: list[float], improved: list[float]) -> dict[str, Any]:
    """Wilcoxon signed-rank when n>=6, else paired t-test. Returns p and mean Δ."""
    if len(baseline) != len(improved) or not baseline:
        return {"n": 0, "mean_delta": None, "p_value": None, "test": None}
    deltas = [i - b for b, i in zip(baseline, improved, strict=True)]
    mean_delta = float(np.mean(deltas))
    if all(d == 0 for d in deltas):
        return {"n": len(deltas), "mean_delta": 0.0, "p_value": 1.0, "test": "constant"}
    if len(deltas) >= 6:
        stat = stats.wilcoxon(deltas)
        return {
            "n": len(deltas),
            "mean_delta": mean_delta,
            "p_value": float(stat.pvalue),
            "test": "wilcoxon",
        }
    stat = stats.ttest_rel(improved, baseline)
    return {
        "n": len(deltas),
        "mean_delta": mean_delta,
        "p_value": float(stat.pvalue),
        "test": "ttest_rel",
    }


def wilson_ci(successes: int, n: int) -> dict[str, float | None]:
    """Wilson score interval for a binomial proportion."""
    if n <= 0:
        return {"n": 0, "rate": None, "ci_low": None, "ci_high": None}
    result = stats.binomtest(successes, n)
    interval = result.proportion_ci(confidence_level=0.95, method="wilson")
    return {
        "n": n,
        "rate": successes / n,
        "ci_low": float(interval.low),
        "ci_high": float(interval.high),
    }


def _norm_skill(name: str) -> str:
    """Normalize skill ids across corpus prefixes and kebab/underscore."""
    return name.split("/")[-1].split("#")[0].replace("-", "_").strip().lower()


def _pair_key(row: TsrRun) -> tuple[str, str, str, int]:
    """Pair native/improved on agent, model, scenario, and repeat."""
    return (row.agent_id, row.model_id, row.scenario_id, row.repeat)


def paired_runs(
    tsr: list[TsrRun],
    *,
    agent_id: str | None = None,
    model_id: str | None = None,
) -> list[tuple[TsrRun, TsrRun]]:
    """Return native/improved pairs that both completed."""
    native: dict[tuple[str, str, str, int], TsrRun] = {}
    improved: dict[tuple[str, str, str, int], TsrRun] = {}
    for row in tsr:
        if row.skipped:
            continue
        if agent_id is not None and row.agent_id != agent_id:
            continue
        if model_id is not None and row.model_id != model_id:
            continue
        key = _pair_key(row)
        if row.arm == "native":
            native[key] = row
        elif row.arm == "improved":
            improved[key] = row
    return [(native[k], improved[k]) for k in sorted(set(native) & set(improved))]


def pair_exclusions(tsr: list[TsrRun]) -> dict[str, int]:
    """Count paired rows versus one-sided or skipped repeats."""
    native: set[tuple[str, str, str, int]] = set()
    improved: set[tuple[str, str, str, int]] = set()
    skipped = 0
    for row in tsr:
        if row.skipped:
            skipped += 1
            continue
        key = _pair_key(row)
        if row.arm == "native":
            native.add(key)
        elif row.arm == "improved":
            improved.add(key)
    return {
        "paired": len(native & improved),
        "native_only": len(native - improved),
        "improved_only": len(improved - native),
        "skipped": skipped,
    }


def _arm_pairs(
    tsr: list[TsrRun],
    *,
    agent_id: str | None = None,
    model_id: str | None = None,
) -> tuple[list[float], list[float], list[float], list[float]]:
    """Return paired native/improved weighted scores and token counts."""
    pairs = paired_runs(tsr, agent_id=agent_id, model_id=model_id)
    nw = [native.weighted for native, _improved in pairs]
    iw = [improved.weighted for _native, improved in pairs]
    nt = [
        float(native.tokens)
        for native, improved in pairs
        if native.tokens is not None and improved.tokens is not None
    ]
    it = [
        float(improved.tokens)
        for native, improved in pairs
        if native.tokens is not None and improved.tokens is not None
    ]
    return nw, iw, nt, it


def _strict_rates(
    tsr: list[TsrRun],
    *,
    agent_id: str | None = None,
    model_id: str | None = None,
) -> dict[str, dict[str, float | None]]:
    """Wilson CI on strict pass rate per arm."""
    out: dict[str, dict[str, float | None]] = {}
    for arm in ("native", "improved"):
        pairs = paired_runs(tsr, agent_id=agent_id, model_id=model_id)
        flags = [
            (r.strict if arm == "native" else i.strict) for r, i in pairs
        ]
        out[arm] = wilson_ci(sum(1 for f in flags if f), len(flags))
    return out


def _skill_mean_tsr_delta(
    tsr: list[TsrRun],
    *,
    agent_id: str | None = None,
    model_id: str | None = None,
) -> dict[str, float]:
    """Mean weighted-TSR Δ per scenario skill within one (agent, model)."""
    native: dict[str, list[float]] = defaultdict(list)
    improved: dict[str, list[float]] = defaultdict(list)
    for row in tsr:
        if row.skipped:
            continue
        if agent_id is not None and row.agent_id != agent_id:
            continue
        if model_id is not None and row.model_id != model_id:
            continue
        skill = _norm_skill(row.skill or row.scenario_id)
        if row.arm == "native":
            native[skill].append(row.weighted)
        elif row.arm == "improved":
            improved[skill].append(row.weighted)
    deltas: dict[str, float] = {}
    for skill in set(native) & set(improved):
        n_mean = sum(native[skill]) / len(native[skill])
        i_mean = sum(improved[skill]) / len(improved[skill])
        deltas[skill] = i_mean - n_mean
    return deltas


def _spearman_skill_paired(
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    *,
    agent_id: str | None = None,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Spearman of NVIDIA quality Δ vs mean TSR Δ, paired by skill id."""
    nvidia_d: dict[str, float] = {}
    for item in deltas:
        if item.baseline_quality is None or item.improved_quality is None:
            continue
        nvidia_d[_norm_skill(item.skill_id)] = item.improved_quality - item.baseline_quality
    tsr_d = _skill_mean_tsr_delta(tsr, agent_id=agent_id, model_id=model_id)
    keys = sorted(set(nvidia_d) & set(tsr_d))
    if len(keys) < 3:
        return {
            "rho": None,
            "p_value": None,
            "n": len(keys),
            "note": "Need paired per-skill NVIDIA Δ and TSR Δ; n is small.",
            "skills": keys,
        }
    rho, p_rho = stats.spearmanr([nvidia_d[k] for k in keys], [tsr_d[k] for k in keys])
    return {
        "rho": float(rho) if rho == rho else None,
        "p_value": float(p_rho) if p_rho == p_rho else None,
        "n": len(keys),
        "note": "Paired by skill id within one (agent, model). Exploratory; n is small.",
        "skills": keys,
    }


def _slice_summary(tsr: list[TsrRun], *, agent_id: str, model_id: str) -> dict[str, Any]:
    """Layer B stats for one agent tree and one actor model."""
    nw, iw, nt, it = _arm_pairs(tsr, agent_id=agent_id, model_id=model_id)
    return {
        "agent_id": agent_id,
        "model_id": model_id,
        "tsr_weighted": {
            **paired_delta_test(nw, iw),
            "baseline": _mean_ci(nw),
            "improved": _mean_ci(iw),
        },
        "tsr_strict": _strict_rates(tsr, agent_id=agent_id, model_id=model_id),
        "tokens_per_task": {
            **paired_delta_test(nt, it),
            "baseline": _mean_ci(nt),
            "improved": _mean_ci(it),
        },
    }


def summarize_run(
    nvidia: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
) -> dict[str, Any]:
    """Build the ``stats`` object written into ``results.json``."""
    del nvidia  # Layer A headline uses improver pairs only.
    quality_pairs: list[tuple[float, float]] = []
    for item in deltas:
        if item.baseline_quality is not None and item.improved_quality is not None:
            quality_pairs.append((item.baseline_quality, item.improved_quality))
    quality_test = paired_delta_test(
        [p[0] for p in quality_pairs],
        [p[1] for p in quality_pairs],
    )

    by_model: list[dict[str, Any]] = []
    model_ids = sorted({r.model_id for r in tsr if not r.skipped} | {r.model_id for r in tsr})
    agent_ids = sorted({r.agent_id for r in tsr})
    for agent_id in agent_ids or ["rasano"]:
        for model_id in model_ids or ["default"]:
            slice_rows = [
                r for r in tsr if r.agent_id == agent_id and r.model_id == model_id
            ]
            if not slice_rows:
                continue
            by_model.append(_slice_summary(tsr, agent_id=agent_id, model_id=model_id))

    # Total = equal-weight mean of per-model means (drop models with no TSR).
    weighted_native: list[float] = []
    weighted_improved: list[float] = []
    strict_native: list[float] = []
    strict_improved: list[float] = []
    tokens_native: list[float] = []
    tokens_improved: list[float] = []
    for block in by_model:
        tw = block["tsr_weighted"]
        bmean = (tw.get("baseline") or {}).get("mean")
        imean = (tw.get("improved") or {}).get("mean")
        if bmean is not None and imean is not None:
            weighted_native.append(float(bmean))
            weighted_improved.append(float(imean))
        ts = block["tsr_strict"]
        nr = (ts.get("native") or {}).get("rate")
        ir = (ts.get("improved") or {}).get("rate")
        if nr is not None and ir is not None:
            strict_native.append(float(nr))
            strict_improved.append(float(ir))
        tok = block["tokens_per_task"]
        tb = (tok.get("baseline") or {}).get("mean")
        ti = (tok.get("improved") or {}).get("mean")
        if tb is not None and ti is not None:
            tokens_native.append(float(tb))
            tokens_improved.append(float(ti))

    total = {
        "tsr_weighted": {
            **paired_delta_test(weighted_native, weighted_improved),
            "baseline": _mean_ci(weighted_native),
            "improved": _mean_ci(weighted_improved),
            "note": "Equal-weight mean of per-model means; models with no TSR dropped.",
        },
        "tsr_strict": {
            "native": _mean_ci(strict_native),
            "improved": _mean_ci(strict_improved),
        },
        "tokens_per_task": {
            **paired_delta_test(tokens_native, tokens_improved),
            "baseline": _mean_ci(tokens_native),
            "improved": _mean_ci(tokens_improved),
        },
    }

    # Headline Spearman is pooled across models (per-slice ρ stays on by_model).
    pooled = _spearman_skill_paired(deltas, tsr)
    if pooled.get("rho") is not None:
        pooled["note"] = (
            "Paired by skill id across models. Exploratory; n is small."
        )
    spearman = pooled
    for block in by_model:
        pair = _spearman_skill_paired(
            deltas,
            tsr,
            agent_id=block["agent_id"],
            model_id=block["model_id"],
        )
        block["spearman_nvidia_vs_tsr"] = pair

    nw_tok, iw_tok = _arm_pairs(tsr)[2], _arm_pairs(tsr)[3]

    nw_all, iw_all, _, _ = _arm_pairs(tsr)
    components = ("skill_started", "tool_correct", "memory_set", "confirmation", "safety")
    component_means: dict[str, dict[str, float | None]] = {}
    for name in components:
        for arm in ("native", "improved"):
            values = [
                getattr(r.components, name)
                for r in tsr
                if r.arm == arm and not r.skipped and getattr(r.components, name) is not None
            ]
            key = f"{arm}.{name}"
            component_means[key] = _mean_ci([float(v) for v in values if v is not None])

    return {
        "nvidia_quality": {
            **quality_test,
            "baseline": _mean_ci([p[0] for p in quality_pairs]),
            "improved": _mean_ci([p[1] for p in quality_pairs]),
        },
        "tsr_weighted": {
            **paired_delta_test(nw_all, iw_all),
            "baseline": _mean_ci(nw_all),
            "improved": _mean_ci(iw_all),
        },
        "tsr_strict": _strict_rates(tsr),
        "tokens_per_task": {
            **paired_delta_test(nw_tok, iw_tok),
            "baseline": _mean_ci(nw_tok),
            "improved": _mean_ci(iw_tok),
        },
        "by_model": by_model,
        "total": total,
        "spearman_nvidia_vs_tsr": spearman,
        "tsr_components": component_means,
        "pair_exclusions": pair_exclusions(tsr),
    }
