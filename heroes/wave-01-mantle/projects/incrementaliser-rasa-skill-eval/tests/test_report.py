"""Report template filler stays clean and resolves placeholders."""

from __future__ import annotations

from rasa_skill_eval.config import load_config
from rasa_skill_eval.models import (
    DeepEvalResult,
    ImproverDelta,
    IntegrationIssue,
    NvidiaSkillResult,
    TsrRun,
)
from rasa_skill_eval.report import (
    build_report_values,
    extra_deepeval_metrics_markdown,
    fill_report_template,
    metrics_table_rows,
    render_integration_issues,
    write_shareable_report,
)
from rasa_skill_eval.stats import summarize_run


def _split_appendix(text: str) -> tuple[str, str]:
    """Return (main body, appendix) for a filled report."""
    body, appendix = text.split("## Appendix", 1)
    return body, appendix


def test_fill_report_unresolved_is_na() -> None:
    """Missing placeholders become n/a, not left as braces."""
    out = fill_report_template("x={{missing}}", {})
    assert out == "x=n/a"
    assert "{{" not in out


def test_metrics_table_never_includes_skip_reason() -> None:
    """CLI logs must not leak into markdown cells."""
    nvidia = [
        NvidiaSkillResult(
            skill_id="rasano/check-balance",
            command="rubric-eval",
            skipped=True,
            skip_reason="rubric CLI not found\nERROR OPENAI_API_KEY",
        )
    ]
    tsr = [
        TsrRun(
            scenario_id="s",
            arm="native",
            repeat=0,
            skipped=True,
            skip_reason="rasa train failed OPENAI_API_KEY",
        )
    ]
    rows = metrics_table_rows(nvidia, tsr, [])
    blob = "\n".join("|".join(r) for r in rows)
    assert "OPENAI_API_KEY" not in blob
    assert "rubric CLI" not in blob.lower()
    assert "skip_reason" not in blob
    assert any(row[1] == "task completion" for row in rows)
    assert any(row[1] == "skill lift" for row in rows)
    assert not any(row[1] == "GEval tool correctness" for row in rows)
    extra = extra_deepeval_metrics_markdown([])
    assert "GEval tool correctness" in extra
    assert "OPENAI_API_KEY" not in extra


def test_write_shareable_report_from_template(tmp_path) -> None:
    """Filled run report matches the long-form headings and keeps extra detail in the appendix."""
    cfg = load_config()
    deltas = [
        ImproverDelta(
            skill_id="rasano/intro",
            baseline_quality=80.0,
            improved_quality=82.0,
            mode="llm",
        )
    ]
    stats = summarize_run([], deltas, [])
    dest = tmp_path / "REPORT.md"
    write_shareable_report(
        dest,
        cfg,
        [],
        [],
        deltas,
        [],
        [],
        stats,
        assessed_on="2026-09-10",
    )
    text = dest.read_text(encoding="utf-8")
    body, appendix = _split_appendix(text)
    assert "{{" not in text
    assert "2026-09-10" in text
    assert "OPENAI_API_KEY" not in text
    assert "## Definitions" in body
    assert "## Problem" in body
    assert "## Methodology" in body
    assert "## Scenarios" in body
    assert "## Mantle Limitations" in body
    assert "![NVIDIA quality](plots/quality_delta.png)" in body
    assert "plots/nvidia_vs_tsr.png" in body
    assert "plots/nvidia_vs_tsr_strict.png" not in body
    assert "plots/deepeval_by_metric.png" not in body
    assert "plots/rubric_delta.png" in appendix
    assert "plots/deepeval_by_metric.png" in appendix
    assert "plots/deepeval_vs_tsr.png" in appendix
    assert "Equal-weight mean of per-model means" not in body
    assert "Equal-weight mean of per-model means" in appendix
    assert "| DeepEval | task completion |" in body
    assert "GEval tool correctness" not in body
    assert "GEval tool correctness" in appendix
    assert "DeepEval task completion" not in body
    assert "DeepEval task completion" in appendix
    assert "What we ran" in appendix
    assert "Scope mix" in appendix
    assert "Asks for Rasa" in appendix
    assert "nvidia/nemotron-3-super-120b-a12b" in text
    assert "nvidia/nvidia/" not in text
    assert "Mantle / Rasa issues this run" in body
    assert "_None this run._" in body
    assert "Harness notes: none." in body
    assert not (tmp_path / "HEROES_REPORT.md").exists()


def test_render_integration_issues_asks_to_report() -> None:
    """Engine findings tell the reader to file them with Rasa."""
    issue = IntegrationIssue(
        code="memory.session_in_prose",
        message="session.foo in instruction prose",
        agent_id="rasano",
        model_id="lfm-1.2b",
        arm="improved",
        report_upstream=True,
        suggested_ask="Either substitute session.* in prose like if:.",
        workaround_applied="rewrote 1 token",
        workaround_succeeded=True,
    )
    text = render_integration_issues([issue])
    assert "Report this to Rasa" in text
    assert "rasano/lfm-1.2b/improved" in text
    assert "train recovered" in text


def test_appendix_asks_for_rasa(tmp_path) -> None:
    """Appendix Asks for Rasa includes the static list plus this run's suggested ask."""
    cfg = load_config()
    dest = tmp_path / "REPORT.md"
    write_shareable_report(
        dest,
        cfg,
        [],
        [],
        [],
        [],
        [],
        summarize_run([], [], []),
        integration_issues=[
            IntegrationIssue(
                code="memory.session_in_prose",
                message="prose",
                report_upstream=True,
                suggested_ask="Document @memory.* so LLM rewrites cannot untrain.",
            )
        ],
    )
    text = dest.read_text(encoding="utf-8")
    _, appendix = _split_appendix(text)
    assert "Document @memory.*" in appendix
    assert "Accept `SKILL.md`" in appendix


def test_heroes_writer_removed() -> None:
    """HEROES_REPORT.md is no longer generated as a separate file."""
    import rasa_skill_eval.report as report

    assert not hasattr(report, "write_heroes_report")


def test_build_report_values_include_agents() -> None:
    """Actor list from config.yaml appears in filled values."""
    cfg = load_config()
    values = build_report_values(cfg, [], [], [], [], [], {})
    assert "lfm-1.2b" in values["agent_models"]
    assert "llama-8b" in values["agent_models"]
    assert values["agent_models_completed"] == "none"
    assert "lfm-1.2b" in values["model_roles_table"]
    assert "1–2B" in values["layer_b_actor_tiers"]


def test_build_report_values_distinguish_configured_from_completed() -> None:
    """Reports keep the configured actor list even when only one produced TSR."""
    cfg = load_config()
    tsr = [
        TsrRun(
            scenario_id="s",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.5,
        ),
        TsrRun(
            scenario_id="s",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=0.6,
        ),
        TsrRun(
            scenario_id="s",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            skipped=True,
            skip_reason="startup failed",
        ),
    ]
    values = build_report_values(cfg, [], [], [], tsr, [], summarize_run([], [], tsr))
    assert "llama-8b" in values["agent_models"]
    assert "`lfm-1.2b`" in values["agent_models_completed"]
    assert "llama-8b" not in values["agent_models_completed"]
    assert "Actors failed or skipped: `llama-8b`" in values["harness_notes"]
    assert "#### `personalization` / `gemma4-31b`" in values["layer_b_by_model"]
    assert "DeepEval task completion" not in values["layer_b_by_model"]
    assert "DeepEval task completion" in values["appendix"]


def test_build_report_values_lists_unexecuted_stages() -> None:
    """Skipped-only NVIDIA and DeepEval stages remain visible in harness notes."""
    cfg = load_config()
    nvidia = [
        NvidiaSkillResult(
            skill_id="rasano/check-balance",
            command="rubric-eval",
            skipped=True,
        )
    ]
    values = build_report_values(
        cfg,
        [],
        nvidia,
        [],
        [],
        [],
        summarize_run(nvidia, [], []),
    )
    assert "Unexecuted evaluation stages: `rubric-eval`." in values["harness_notes"]


def test_harness_notes_deepeval_produced_no_scores() -> None:
    """Metric API failures are not reported as an unexecuted DeepEval stage."""
    cfg = load_config()
    deepeval = [
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="task_completion",
            skipped=True,
            skip_reason="LLMTestCase missing tools_called",
        )
    ]
    values = build_report_values(cfg, [], [], [], [], deepeval, summarize_run([], [], []))
    assert "DeepEval produced no scores" in values["harness_notes"]
    assert "DeepEval coverage: `task_completion` 0/1" in values["harness_notes"]
    assert "Unexecuted evaluation stages: `deepeval`" not in values["harness_notes"]


def test_harness_notes_deepeval_coverage_uses_tsr_denominator() -> None:
    """Silent DeepEval drops must not shrink the expected count."""
    from rasa_skill_eval.report import harness_notes_text

    tsr = [
        TsrRun(
            scenario_id="faq",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
        ),
        TsrRun(
            scenario_id="faq",
            arm="improved",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
        ),
    ]
    deepeval = [
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="task_completion",
            score=0.5,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        )
    ]
    notes = harness_notes_text([], deepeval=deepeval, tsr=tsr)
    assert "`task_completion` 1/2" in notes


def test_harness_notes_schema_high_and_imported() -> None:
    """SCHEMA HIGH and donated Layer A are harness notes, not silent success."""
    cfg = load_config()
    nvidia = [
        NvidiaSkillResult(
            skill_id="rasano/check-balance",
            command="validate",
            schema_high=["Missing required heading: # Title"],
        )
    ]
    values = build_report_values(
        cfg,
        [],
        nvidia,
        [ImproverDelta(skill_id="rasano/check-balance", mode="llm")],
        [],
        [],
        summarize_run(nvidia, [], []),
        imported_from="runs/zfiles",
        kimi_skipped=True,
    )
    assert "NVIDIA SCHEMA HIGH" in values["harness_notes"]
    assert "Report this to Rasa" in values["harness_notes"]
    assert "Kimi was not called" in values["harness_notes"]
    assert "runs/zfiles" in values["harness_notes"]


def test_harness_notes_heuristic_improver_phrasing() -> None:
    """Failed/heuristic improver rows use the published harness-notes sentence."""
    cfg = load_config()
    values = build_report_values(
        cfg,
        [],
        [],
        [ImproverDelta(skill_id="rasano/add-payee", mode="heuristic")],
        [],
        [],
        summarize_run([], [], []),
    )
    notes = values["harness_notes"]
    assert "Improver LLM failed for: `rasano/add-payee`." in notes
    assert "Heuristic rewrite used; Layer A A/B is weaker for those skills." in notes
