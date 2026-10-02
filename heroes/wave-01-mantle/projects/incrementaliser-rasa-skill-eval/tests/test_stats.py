"""Stats helpers: pairing, Spearman by skill, Layer A improver pairs."""

from __future__ import annotations

import pytest

from rasa_skill_eval.models import ImproverDelta, TsrComponents, TsrRun
from rasa_skill_eval.stats import paired_delta_test, summarize_run, wilson_ci


def test_paired_constant_delta() -> None:
    """All-zero deltas yield p=1."""
    out = paired_delta_test([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
    assert out["mean_delta"] == 0.0
    assert out["p_value"] == 1.0


def test_wilson_all_pass() -> None:
    """3/3 successes sit near 1 with a wide small-n interval."""
    out = wilson_ci(3, 3)
    assert out["rate"] == 1.0
    assert out["ci_low"] is not None and out["ci_low"] < 1.0


def test_summarize_run_quality_pairs() -> None:
    """Improver deltas feed the NVIDIA quality test."""
    deltas = [
        ImproverDelta(
            skill_id="a",
            baseline_quality=80.0,
            improved_quality=86.0,
        ),
        ImproverDelta(
            skill_id="b",
            baseline_quality=82.0,
            improved_quality=88.0,
        ),
    ]
    tsr = [
        TsrRun(
            scenario_id="s",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            components=TsrComponents(skill_started=1.0),
            weighted=0.5,
            strict=False,
        ),
        TsrRun(
            scenario_id="s",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            components=TsrComponents(skill_started=1.0),
            weighted=0.8,
            strict=True,
        ),
    ]
    stats = summarize_run([], deltas, tsr)
    assert stats["nvidia_quality"]["mean_delta"] == 6.0
    assert stats["tsr_weighted"]["mean_delta"] == pytest.approx(0.3)


def test_tsr_pairs_by_scenario_repeat_not_list_order() -> None:
    """Native/improved must align on (agent, model, scenario, repeat)."""
    tsr = [
        TsrRun(
            scenario_id="a",
            skill="check_balance",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="m",
            weighted=0.2,
        ),
        TsrRun(
            scenario_id="b",
            skill="transfer_money",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="m",
            weighted=0.4,
        ),
        # Improved rows deliberately reversed vs native list order.
        TsrRun(
            scenario_id="b",
            skill="transfer_money",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="m",
            weighted=0.9,
        ),
        TsrRun(
            scenario_id="a",
            skill="check_balance",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="m",
            weighted=0.5,
        ),
    ]
    stats = summarize_run([], [], tsr)
    # Paired deltas: a 0.5-0.2=0.3, b 0.9-0.4=0.5 → mean 0.4
    assert stats["tsr_weighted"]["mean_delta"] == pytest.approx(0.4)


def test_spearman_pairs_by_skill() -> None:
    """Spearman uses skill-mean TSR Δ, not scenario-repeat zip."""
    deltas = [
        ImproverDelta(
            skill_id="rasano/check-balance",
            baseline_quality=80.0,
            improved_quality=90.0,
        ),
        ImproverDelta(
            skill_id="rasano/transfer-money",
            baseline_quality=80.0,
            improved_quality=82.0,
        ),
        ImproverDelta(skill_id="rasano/intro", baseline_quality=80.0, improved_quality=81.0),
    ]
    tsr: list[TsrRun] = []
    for skill, n_w, i_w in (
        ("check_balance", 0.2, 0.8),
        ("transfer_money", 0.5, 0.6),
        ("intro", 0.4, 0.5),
    ):
        for arm, w in (("native", n_w), ("improved", i_w)):
            tsr.append(
                TsrRun(
                    scenario_id=f"s_{skill}",
                    skill=skill,
                    arm=arm,
                    repeat=0,
                    agent_id="rasano",
                    model_id="m",
                    weighted=w,
                )
            )
    stats = summarize_run([], deltas, tsr)
    spearman = stats["spearman_nvidia_vs_tsr"]
    assert spearman["n"] == 3
    assert spearman["rho"] is not None
    assert "skill" in (spearman.get("note") or "").lower()


def test_headline_spearman_pools_across_models() -> None:
    """Headline ρ is not taken from the first (agent, model) slice only."""
    deltas = [
        ImproverDelta(
            skill_id="rasano/check-balance",
            baseline_quality=80.0,
            improved_quality=90.0,
        ),
        ImproverDelta(
            skill_id="rasano/transfer-money",
            baseline_quality=80.0,
            improved_quality=82.0,
        ),
        ImproverDelta(skill_id="rasano/intro", baseline_quality=80.0, improved_quality=81.0),
    ]
    tsr: list[TsrRun] = []
    for model_id in ("m1", "m2"):
        for skill, n_w, i_w in (
            ("check_balance", 0.2, 0.8),
            ("transfer_money", 0.5, 0.6),
            ("intro", 0.4, 0.5),
        ):
            for arm, w in (("native", n_w), ("improved", i_w)):
                tsr.append(
                    TsrRun(
                        scenario_id=f"s_{skill}",
                        skill=skill,
                        arm=arm,
                        repeat=0,
                        agent_id="rasano",
                        model_id=model_id,
                        weighted=w,
                    )
                )
    stats = summarize_run([], deltas, tsr)
    assert stats["spearman_nvidia_vs_tsr"]["n"] == 3
    assert "across models" in (stats["spearman_nvidia_vs_tsr"].get("note") or "")
    assert all("spearman_nvidia_vs_tsr" in block for block in stats["by_model"])


def test_by_model_and_total_present() -> None:
    """Factorial stats expose per-model blocks and a total mean."""
    tsr = []
    for model_id, native_w, improved_w in (("8b", 0.4, 0.6), ("70b", 0.5, 0.7)):
        for arm, w in (("native", native_w), ("improved", improved_w)):
            tsr.append(
                TsrRun(
                    scenario_id="s",
                    arm=arm,
                    repeat=0,
                    agent_id="rasano",
                    model_id=model_id,
                    weighted=w,
                )
            )
    stats = summarize_run([], [], tsr)
    assert len(stats["by_model"]) == 2
    assert stats["total"]["tsr_weighted"]["mean_delta"] == pytest.approx(0.2)


def test_pair_exclusions_count_asymmetric_timeouts() -> None:
    """Improved-only timeouts must not silently drop out of the exclusion tally."""
    from rasa_skill_eval.stats import pair_exclusions

    tsr = [
        TsrRun(scenario_id="a", arm="native", repeat=0, weighted=1.0),
        TsrRun(scenario_id="a", arm="improved", repeat=0, skipped=True, skip_reason="timed out"),
        TsrRun(scenario_id="b", arm="native", repeat=0, weighted=0.5),
        TsrRun(scenario_id="b", arm="improved", repeat=0, weighted=0.6),
    ]
    out = pair_exclusions(tsr)
    assert out["paired"] == 1
    assert out["native_only"] == 1
    assert out["skipped"] == 1
