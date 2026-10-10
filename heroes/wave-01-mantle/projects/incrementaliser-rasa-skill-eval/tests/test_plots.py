"""TSR plots skip empty placeholders when observations exist."""

from __future__ import annotations

from pathlib import Path

from rasa_skill_eval.models import DeepEvalResult, ImproverDelta, NvidiaSkillResult, TsrRun
from rasa_skill_eval.plots import (
    _mean_by_model,
    _mean_by_scenario,
    _mean_by_tier,
    _mean_tsr_by_skill,
    model_size_tier,
    write_plots,
)


def test_mean_by_scenario_ignores_skipped() -> None:
    """Empty plots were caused by every TSR row being skipped."""
    rows = [
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=0,
            agent_id="rasano",
            skipped=True,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=1,
            agent_id="rasano",
            skipped=False,
            weighted=0.8,
        ),
    ]
    assert _mean_by_scenario(rows, "native")["rasano:balance_named"] == 0.8
    assert _mean_tsr_by_skill(rows, "native")["check_balance"] == 0.8


def test_model_size_tier_mapping() -> None:
    """Classify model names into 1-2B, 8B, 30B tiers."""
    assert model_size_tier("lfm-1.2b") == "1–2B"
    assert model_size_tier("lfm-2.6b") == "1–2B"
    assert model_size_tier("llama-8b") == "8B"
    assert model_size_tier("nemotron-8b") == "8B"
    assert model_size_tier("muse-30b") == "30B"
    assert model_size_tier("gemma4-31b") == "30B"
    assert model_size_tier("custom-unknown") == "Other"


def test_write_plots_emits_model_and_tier_charts(tmp_path: Path) -> None:
    """Plots must generate individual model and size tier comparison figures."""
    deltas = [
        ImproverDelta(
            skill_id="rasano/check-balance",
            baseline_quality=80.0,
            improved_quality=84.0,
        )
    ]
    tsr = [
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=0,
            model_id="lfm-1.2b",
            weighted=0.5,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="improved",
            repeat=0,
            model_id="lfm-1.2b",
            weighted=0.7,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=0,
            model_id="llama-8b",
            weighted=0.6,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="improved",
            repeat=0,
            model_id="llama-8b",
            weighted=0.8,
        ),
    ]
    tier_native = _mean_by_tier(tsr, "native")
    tier_improved = _mean_by_tier(tsr, "improved")
    assert tier_native["1–2B"] == 0.5
    assert tier_improved["1–2B"] == 0.7
    assert tier_native["8B"] == 0.6
    assert tier_improved["8B"] == 0.8

    model_native = _mean_by_model(tsr, "native")
    assert model_native["lfm-1.2b"] == 0.5
    assert model_native["llama-8b"] == 0.6

    paths = write_plots(tmp_path, deltas, tsr)
    names = {p.name for p in paths}
    assert "tsr_weighted.png" in names
    assert "tsr_by_model.png" in names
    assert "tsr_by_model_size.png" in names
    assert "nvidia_vs_tsr.png" in names
    assert "nvidia_vs_tsr_strict.png" in names
    assert (tmp_path / "tsr_by_model_size.png").stat().st_size > 500
    assert (tmp_path / "tsr_by_model.png").stat().st_size > 500
    assert (tmp_path / "nvidia_vs_tsr_strict.png").stat().st_size > 500


def test_write_plots_emits_deepeval_and_rubric_charts(tmp_path: Path) -> None:
    """DeepEval and NVIDIA rubric figures are written with scored rows only."""
    deltas = [
        ImproverDelta(
            skill_id="rasano/check-balance",
            baseline_quality=80.0,
            improved_quality=84.0,
        )
    ]
    tsr = [
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.5,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.7,
        ),
    ]
    nvidia = [
        NvidiaSkillResult(
            skill_id="rasano/check-balance",
            command="rubric-eval",
            rubric_score=70.0,
        ),
        NvidiaSkillResult(
            skill_id="rasano/check-balance#improved",
            command="rubric-eval",
            rubric_score=80.0,
        ),
        NvidiaSkillResult(
            skill_id="rasano/intro",
            command="rubric-eval",
            skipped=True,
            rubric_score=None,
        ),
    ]
    deepeval = [
        DeepEvalResult(
            scenario_id="balance_named",
            arm="native",
            metric="task_completion",
            score=0.4,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
        DeepEvalResult(
            scenario_id="balance_named",
            arm="improved",
            metric="task_completion",
            score=0.6,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
        DeepEvalResult(
            scenario_id="balance_named",
            arm="native",
            metric="g_eval_tool_correctness",
            skipped=True,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
    ]
    paths = write_plots(tmp_path, deltas, tsr, deepeval=deepeval, nvidia=nvidia)
    names = {path.name for path in paths}
    assert "rubric_delta.png" in names
    assert "deepeval_by_metric.png" in names
    assert "deepeval_by_model.png" in names
    assert "deepeval_by_model_size.png" in names
    assert "deepeval_by_scenario.png" in names
    assert "deepeval_task_completion_by_model.png" in names
    assert "deepeval_g_eval_tool_correctness_by_model.png" in names
    assert "deepeval_vs_tsr.png" in names
    assert (tmp_path / "rubric_delta.png").stat().st_size > 500
    assert (tmp_path / "deepeval_by_metric.png").stat().st_size > 500


def test_deepeval_and_rubric_plots_use_planned_universe() -> None:
    """Missing improved DeepEval scores still reserve axis categories and n=planned."""
    from rasa_skill_eval.plots import (
        _deepeval_expected,
        _rubric_pairs,
        _tsr_model_ids,
        _tsr_scenario_labels,
    )

    tsr = [
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.5,
        ),
        TsrRun(
            scenario_id="balance_named",
            skill="check_balance",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.7,
        ),
        TsrRun(
            scenario_id="faq_grounded",
            skill="banking_faq",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            weighted=0.4,
        ),
        TsrRun(
            scenario_id="faq_grounded",
            skill="banking_faq",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            weighted=0.6,
        ),
    ]
    deepeval = [
        DeepEvalResult(
            scenario_id="balance_named",
            arm="native",
            metric="task_completion",
            score=0.4,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        )
    ]
    assert _deepeval_expected(tsr, deepeval, "task_completion") == 4
    assert _tsr_model_ids(tsr) == ["lfm-1.2b", "llama-8b"]
    assert "rasano:faq_grounded" in _tsr_scenario_labels(tsr)
    nvidia = [
        NvidiaSkillResult(
            skill_id="rasano/check-balance",
            command="rubric-eval",
            rubric_score=70.0,
        ),
        NvidiaSkillResult(
            skill_id="rasano/check-balance#improved",
            command="rubric-eval",
            skipped=True,
        ),
        NvidiaSkillResult(
            skill_id="rasano/intro",
            command="rubric-eval",
            skipped=True,
        ),
    ]
    labels, baseline, improved, counts = _rubric_pairs(nvidia)
    assert "rasano/intro" in labels
    assert "rasano/check-balance" in labels
    assert baseline[labels.index("rasano/check-balance")] == 70.0
    assert improved[labels.index("rasano/check-balance")] is None
    assert counts == (1, 3)
