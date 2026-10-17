"""Write run-folder markdown from the committed docs/REPORT.md template."""

from __future__ import annotations

import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from rasa_skill_eval import PROJECT_ROOT
from rasa_skill_eval.config import AppConfig, LlmEndpointSettings
from rasa_skill_eval.models import (
    DeepEvalResult,
    ImproverDelta,
    IntegrationIssue,
    MantleInventory,
    NvidiaSkillResult,
    TsrRun,
)
from rasa_skill_eval.nvidia_llm import nvidia_key_configured
from rasa_skill_eval.nvidia_runner import nvidia_command_successful, resolve_skillevaluator
from rasa_skill_eval.plots import model_size_tier
from rasa_skill_eval.stats import paired_runs

_PLACEHOLDER = re.compile(r"\{\{([a-zA-Z0-9_.]+)\}\}")
_NON_EVAL_CORPORA = {"writing_for_agents"}
_T2_CORPUS_ORDER = ("rasano", "personalization")
_TIER_ORDER = ("1–2B", "8B", "30B", "Other")
_EXTRA_DEEPEVAL = (
    ("tool_correctness", "tool correctness", "Judge evaluation of tool choice and arguments"),
    ("answer_relevancy", "answer relevancy", "Judge evaluation of assistant response relevancy"),
    (
        "g_eval_tool_correctness",
        "GEval tool correctness",
        "GEval LLM judge of tool choice and safety",
    ),
)
_DEEPEVAL_DETAIL_ROWS = (
    ("task_completion", "DeepEval task completion"),
    ("answer_relevancy", "DeepEval answer relevancy"),
    ("tool_correctness", "DeepEval tool correctness"),
    ("g_eval_tool_correctness", "DeepEval GEval tool correctness"),
)


def _fmt(value: float | None, digits: int = 2) -> str:
    """Format a number or n/a."""
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def _delta(a: float | None, b: float | None) -> str:
    """Improved minus baseline."""
    if a is None or b is None:
        return "n/a"
    return f"{b - a:+.2f}"


def _mean(values: list[float]) -> float | None:
    """Arithmetic mean or None."""
    if not values:
        return None
    return sum(values) / len(values)


def _endpoint_label(provider: str, model: str) -> str:
    """Return provider/model provenance without duplicating its namespace."""
    return model if model.startswith(f"{provider}/") else f"{provider}/{model}"


def _model_short(model: str) -> str:
    """Return the configured model id without a provider prefix rewrite."""
    return model


def _eval_corpora(config: AppConfig) -> list[str]:
    """Eval corpus ids used in T2 rows and Layer B slices."""
    names = [name for name in config.corpora if name not in _NON_EVAL_CORPORA]
    ordered = [name for name in _T2_CORPUS_ORDER if name in names]
    ordered.extend(sorted(name for name in names if name not in ordered))
    return ordered or list(_T2_CORPUS_ORDER)


def _eval_agent_ids(config: AppConfig) -> list[str]:
    """Layer B agent ids in alphabetical corpus order (personalization, rasano)."""
    return sorted(_eval_corpora(config))


def improver_delta_markdown(deltas: list[ImproverDelta], *, heading: str = "# Improver delta") -> str:
    """Skill-level quality and word-count table used by the standalone file and appendix."""
    lines = [
        heading,
        "",
        "Scores are NVIDIA `quality-check` on **projected** Agent Skills copies.",
        "Native Mantle `skill.md` is not SkillEvaluator input.",
        "`config/mantle.yml` must stay byte-identical after the copy.",
        "Skill-doc length is whitespace word count, not inference tokens.",
        "",
        "| Skill | Mode | Baseline quality | Improved quality | Words before | Words after | Constraints preserved | Changes |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    if not deltas:
        lines.append("| _None._ | n/a | n/a | n/a | n/a | n/a | n/a | n/a |")
    for item in deltas:
        changes = "; ".join(item.changes) if item.changes else "none"
        lines.append(
            f"| {item.skill_id} | {item.mode} | {_fmt(item.baseline_quality, 1)} | "
            f"{_fmt(item.improved_quality, 1)} | {item.baseline_skill_md_words} | "
            f"{item.improved_skill_md_words} | {item.constraints_preserved} | {changes} |"
        )
    return "\n".join(lines)


def write_improver_delta(path: Path, deltas: list[ImproverDelta]) -> None:
    """Write the before/after improver table (run-local only)."""
    path.write_text(improver_delta_markdown(deltas) + "\n", encoding="utf-8")


def metrics_table_rows(
    nvidia: list[NvidiaSkillResult],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
    deltas: list[ImproverDelta] | None = None,
    *,
    extra_deepeval: bool = False,
    corpora: list[str] | None = None,
) -> list[list[str]]:
    """Build [layer, metric, what, baseline, improved, delta] rows.

    Layer A quality means use improver pairs when ``deltas`` is provided.
    Skip reasons never enter cells. Main-body tables omit extra DeepEval metrics.
    """
    rows: list[list[str]] = []
    deltas = deltas or []
    t2_corpora = corpora or list(_T2_CORPUS_ORDER)

    if deltas:
        bq = _mean(
            [d.baseline_quality for d in deltas if d.baseline_quality is not None]
        )
        iq = _mean(
            [d.improved_quality for d in deltas if d.improved_quality is not None]
        )
    else:
        def quality_arm(improved: bool) -> list[float]:
            out: list[float] = []
            for item in nvidia:
                if item.command != "quality-check" or item.quality_score is None:
                    continue
                is_imp = "#improved" in item.skill_id
                if is_imp == improved:
                    out.append(item.quality_score)
            return out

        bq, iq = _mean(quality_arm(False)), _mean(quality_arm(True))

    rows.append(
        [
            "T1 quality",
            "overall 0–100",
            "Offline Agent Skills style linter on **projected** copies (improver pairs)",
            _fmt(bq, 1),
            _fmt(iq, 1),
            _delta(bq, iq),
        ]
    )
    for dim in ("correctness", "discoverability", "reliability", "efficiency"):
        bd = _mean(
            [
                item.dimensions[dim]
                for item in nvidia
                if item.command == "quality-check"
                and dim in item.dimensions
                and "#improved" not in item.skill_id
                and any(
                    _skill_match(item.skill_id, d.skill_id)
                    for d in deltas
                )
            ]
        ) if deltas else _mean(
            [
                item.dimensions[dim]
                for item in nvidia
                if item.command == "quality-check"
                and dim in item.dimensions
                and "#improved" not in item.skill_id
            ]
        )
        id_ = _mean(
            [
                item.dimensions[dim]
                for item in nvidia
                if item.command == "quality-check"
                and dim in item.dimensions
                and "#improved" in item.skill_id
                and any(
                    _skill_match(item.skill_id.replace("#improved", ""), d.skill_id)
                    for d in deltas
                )
            ]
        ) if deltas else _mean(
            [
                item.dimensions[dim]
                for item in nvidia
                if item.command == "quality-check"
                and dim in item.dimensions
                and "#improved" in item.skill_id
            ]
        )
        rows.append(
            [
                "T1 quality",
                dim,
                f"Quality-check {dim} dimension",
                _fmt(bd, 1),
                _fmt(id_, 1),
                _delta(bd, id_),
            ]
        )

    def rubric_arm(improved: bool) -> list[float]:
        return [
            item.rubric_score
            for item in nvidia
            if item.command == "rubric-eval"
            and item.rubric_score is not None
            and (("#improved" in item.skill_id) == improved)
        ]

    br, ir = _mean(rubric_arm(False)), _mean(rubric_arm(True))
    rows.append(
        [
            "T1 rubric",
            "weighted 0–100",
            "LLM judge of skill docs (projected copies)",
            _fmt(br, 1),
            _fmt(ir, 1),
            _delta(br, ir),
        ]
    )

    t2_by_id = {
        item.skill_id: item
        for item in nvidia
        if item.command == "similarity-check"
    }
    for corpus in t2_corpora:
        item = t2_by_id.get(corpus)
        if item is None:
            for skill_id, candidate in t2_by_id.items():
                if corpus in skill_id:
                    item = candidate
                    break
        pairs = item.similarity_pairs if item is not None else None
        rows.append(
            [
                "T2",
                f"similarity ({corpus})",
                "Overlap inside the projected collection",
                str(pairs) if pairs is not None else "n/a",
                "n/a",
                "n/a",
            ]
        )

    def t3_arm(improved: bool) -> list[float]:
        return [
            item.skill_lift
            for item in nvidia
            if item.command == "tier3-evaluate"
            and item.skill_lift is not None
            and (("#improved" in item.skill_id) == improved)
        ]

    t3_b, t3_i = t3_arm(False), t3_arm(True)
    bl, il = _mean(t3_b), _mean(t3_i)
    rows.append(
        [
            "T3",
            "skill lift",
            "Harbor coding-agent with-skill minus without-skill. Not Mantle TSR",
            _fmt(bl),
            _fmt(il),
            _delta(bl, il),
        ]
    )

    def tsr_arm(arm: str, attr: str) -> list[float]:
        out: list[float] = []
        for native, improved in paired_runs(tsr):
            row = native if arm == "native" else improved
            if attr == "weighted":
                out.append(row.weighted)
            elif attr == "strict":
                out.append(1.0 if row.strict else 0.0)
        return out

    bw, iw = _mean(tsr_arm("native", "weighted")), _mean(tsr_arm("improved", "weighted"))
    rows.append(
        [
            "Mantle",
            "TSR (weighted)",
            "Weighted sum of routing / tools / memory / confirmation / safety",
            _fmt(bw),
            _fmt(iw),
            _delta(bw, iw),
        ]
    )
    bs, iss = _mean(tsr_arm("native", "strict")), _mean(tsr_arm("improved", "strict"))
    rows.append(
        [
            "Mantle",
            "TSR (strict)",
            "Fraction of scenario-runs where every applicable assertion passed",
            _fmt(bs),
            _fmt(iss),
            _delta(bs, iss),
        ]
    )

    def tokens(arm: str) -> list[float]:
        out: list[float] = []
        for native, improved in paired_runs(tsr):
            row = native if arm == "native" else improved
            if row.tokens is not None:
                out.append(float(row.tokens))
        return out

    bt, it = _mean(tokens("native")), _mean(tokens("improved"))
    rows.append(
        [
            "Mantle",
            "tokens/task",
            "Prompt+completion tokens when the provider reports usage",
            _fmt(bt, 0),
            _fmt(it, 0),
            _delta(bt, it),
        ]
    )

    deepeval_metrics = [
        ("task_completion", "task completion", "Judge on tracker transcripts (secondary to TSR)"),
    ]
    if extra_deepeval:
        deepeval_metrics.extend(_EXTRA_DEEPEVAL)
    for metric_key, metric_title, metric_desc in deepeval_metrics:
        b_scores = [
            r.score
            for r in deepeval
            if r.arm == "native" and r.score is not None and not r.skipped and r.metric == metric_key
        ]
        i_scores = [
            r.score
            for r in deepeval
            if r.arm == "improved" and r.score is not None and not r.skipped and r.metric == metric_key
        ]
        bd, idd = _mean(b_scores), _mean(i_scores)
        rows.append(
            [
                "DeepEval",
                metric_title,
                metric_desc,
                _fmt(bd),
                _fmt(idd),
                _delta(bd, idd),
            ]
        )
    return rows


def _skill_match(a: str, b: str) -> bool:
    """True when skill ids refer to the same projected skill."""
    na = a.split("#")[0].replace("-", "_").lower()
    nb = b.split("#")[0].replace("-", "_").lower()
    return na == nb or na.endswith("/" + nb.split("/")[-1]) or nb.endswith("/" + na.split("/")[-1])


def render_metrics_markdown(
    nvidia: list[NvidiaSkillResult],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
    deltas: list[ImproverDelta] | None = None,
    *,
    extra_deepeval: bool = False,
    corpora: list[str] | None = None,
) -> str:
    """Markdown table of main-body metrics (no rubric dump)."""
    lines = [
        "| Layer | Metric | What it is | Baseline | Improved | Delta |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in metrics_table_rows(
        nvidia,
        tsr,
        deepeval,
        deltas=deltas,
        extra_deepeval=extra_deepeval,
        corpora=corpora,
    ):
        lines.append("| " + " | ".join(row) + " |")
    return "\n".join(lines)


def extra_deepeval_metrics_markdown(deepeval: list[DeepEvalResult]) -> str:
    """Appendix table for DeepEval metrics omitted from the main body."""
    lines = [
        "| Layer | Metric | What it is | Baseline | Improved | Delta |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for metric_key, metric_title, metric_desc in _EXTRA_DEEPEVAL:
        b_scores = [
            r.score
            for r in deepeval
            if r.arm == "native" and r.score is not None and not r.skipped and r.metric == metric_key
        ]
        i_scores = [
            r.score
            for r in deepeval
            if r.arm == "improved" and r.score is not None and not r.skipped and r.metric == metric_key
        ]
        bd, idd = _mean(b_scores), _mean(i_scores)
        lines.append(
            f"| DeepEval | {metric_title} | {metric_desc} | {_fmt(bd)} | {_fmt(idd)} | {_delta(bd, idd)} |"
        )
    return "\n".join(lines)


def render_rubric_criteria(nvidia: list[NvidiaSkillResult]) -> str:
    """Per-skill NVIDIA rubric criterion scores, or a stable empty marker."""
    rubric_items = [item for item in nvidia if item.command == "rubric-eval" and item.rubric_criteria]
    lines = [
        "NVIDIA `rubric-eval` assesses documentation quality across qualitative criteria using LLM-as-a-judge.",
        "",
        "| Skill / Arm | Criterion | Score |",
        "| --- | --- | --- |",
    ]
    if not rubric_items:
        lines.append("| _None._ | n/a | n/a |")
        return "\n".join(lines)
    for item in rubric_items:
        for crit_name, crit_score in sorted(item.rubric_criteria.items()):
            lines.append(f"| `{item.skill_id}` | {crit_name} | {_fmt(crit_score, 1)} |")
    return "\n".join(lines)


def _layer_b_block(
    block: dict[str, Any],
    deepeval: list[DeepEvalResult] | None = None,
    *,
    detail: bool = False,
) -> str:
    """One per-model Layer B markdown table.

    Main-body tables are TSR/tokens only. Appendix ``detail`` adds Spearman and DeepEval.
    """
    tw = block.get("tsr_weighted") or {}
    ts = block.get("tsr_strict") or {}
    tok = block.get("tokens_per_task") or {}
    agent_id = str(block.get("agent_id") or "")
    model_id = str(block.get("model_id") or "")
    lines = [
        f"#### `{agent_id}` / `{model_id}`",
        "",
        "| Metric | Baseline | Improved | Delta |",
        "| --- | --- | --- | --- |",
        f"| TSR (weighted) | {_fmt((tw.get('baseline') or {}).get('mean'))} | "
        f"{_fmt((tw.get('improved') or {}).get('mean'))} | {_fmt(tw.get('mean_delta'))} |",
        f"| TSR (strict rate) | {_fmt((ts.get('native') or {}).get('rate'))} | "
        f"{_fmt((ts.get('improved') or {}).get('rate'))} | "
        f"{_delta((ts.get('native') or {}).get('rate'), (ts.get('improved') or {}).get('rate'))} |",
        f"| tokens/task | {_fmt((tok.get('baseline') or {}).get('mean'), 0)} | "
        f"{_fmt((tok.get('improved') or {}).get('mean'), 0)} | {_fmt(tok.get('mean_delta'), 0)} |",
    ]
    if detail:
        spear = block.get("spearman_nvidia_vs_tsr") or {}
        if spear.get("rho") is not None:
            lines.append(
                f"| Spearman NVIDIA vs TSR | {_fmt(spear.get('rho'))} | "
                f"n={spear.get('n')} | p={_fmt(spear.get('p_value'))} |"
            )
        for metric_key, metric_title in _DEEPEVAL_DETAIL_ROWS:
            native_mean, improved_mean = _deepeval_means(
                deepeval or [], agent_id=agent_id, model_id=model_id, metric=metric_key
            )
            lines.append(
                f"| {metric_title} | {_fmt(native_mean)} | {_fmt(improved_mean)} | "
                f"{_delta(native_mean, improved_mean)} |"
            )
    lines.append("")
    return "\n".join(lines)


def _deepeval_means(
    rows: list[DeepEvalResult],
    *,
    agent_id: str,
    model_id: str,
    metric: str,
) -> tuple[float | None, float | None]:
    """Native/improved DeepEval means for one actor slice."""
    def arm_mean(arm: str) -> float | None:
        values = [
            float(row.score)
            for row in rows
            if row.agent_id == agent_id
            and row.model_id == model_id
            and row.metric == metric
            and row.arm == arm
            and row.score is not None
            and not row.skipped
        ]
        if not values:
            return None
        return sum(values) / len(values)

    return arm_mean("native"), arm_mean("improved")


def _layer_b_slices(config: AppConfig, stats: dict[str, Any]) -> list[dict[str, Any]]:
    """One stats block per eval corpus × configured actor, n/a when missing."""
    by_model = stats.get("by_model") or []
    index = {
        (str(block.get("agent_id") or ""), str(block.get("model_id") or "")): block
        for block in by_model
    }
    slices: list[dict[str, Any]] = []
    agents = sorted(config.llm.agents, key=lambda actor: actor.path_id())
    if not agents:
        return list(by_model)
    for agent_id in _eval_agent_ids(config):
        for actor in agents:
            model_id = actor.path_id()
            slices.append(index.get((agent_id, model_id)) or {
                "agent_id": agent_id,
                "model_id": model_id,
            })
    return slices


def _layer_b_by_model_markdown(
    config: AppConfig,
    stats: dict[str, Any],
    deepeval: list[DeepEvalResult] | None = None,
    *,
    detail: bool = False,
) -> str:
    """Render Layer B per-model tables for the main body or appendix."""
    blocks = _layer_b_slices(config, stats)
    if not blocks:
        return "_No Layer B rows._"
    return "\n".join(_layer_b_block(block, deepeval, detail=detail) for block in blocks)


def _layer_b_total(stats: dict[str, Any], *, intro: bool = False) -> str:
    """Total Layer B table from equal-weight per-model means."""
    total = stats.get("total") or {}
    tw = total.get("tsr_weighted") or {}
    ts = total.get("tsr_strict") or {}
    tok = total.get("tokens_per_task") or {}
    lines: list[str] = []
    if intro:
        lines.extend(
            [
                "Equal-weight mean of per-model means (each actor counts once):",
                "",
            ]
        )
    lines.extend(
        [
            "| Metric | Baseline | Improved | Delta |",
            "| --- | --- | --- | --- |",
            f"| TSR (weighted) | {_fmt((tw.get('baseline') or {}).get('mean'))} | "
            f"{_fmt((tw.get('improved') or {}).get('mean'))} | {_fmt(tw.get('mean_delta'))} |",
            f"| TSR (strict rate) | {_fmt((ts.get('native') or {}).get('mean'))} | "
            f"{_fmt((ts.get('improved') or {}).get('mean'))} | "
            f"{_delta((ts.get('native') or {}).get('mean'), (ts.get('improved') or {}).get('mean'))} |",
            f"| tokens/task | {_fmt((tok.get('baseline') or {}).get('mean'), 0)} | "
            f"{_fmt((tok.get('improved') or {}).get('mean'), 0)} | {_fmt(tok.get('mean_delta'), 0)} |",
        ]
    )
    return "\n".join(lines)


def render_model_roles_table(config: AppConfig) -> str:
    """Zrepo model-roles table with endpoints from config.yaml."""
    agents = ", ".join(
        f"`{actor.path_id()}` ({_endpoint_label(actor.provider, actor.model)})"
        for actor in config.llm.agents
    ) or "n/a"
    improver = _endpoint_label(config.llm.improver.provider, config.llm.improver.model)
    judge = _endpoint_label(config.llm.judge.provider, config.llm.judge.model)
    embeddings = _endpoint_label(config.llm.embeddings.provider, config.llm.embeddings.model)
    judge_channel = _judge_channel(config.llm.judge.provider)
    return "\n".join(
        [
            "| Role | Config Path | Layer | Default Endpoint | Purpose |",
            "| --- | --- | --- | --- | --- |",
            f"| Improver | `llm.improver` | A | `{improver}` | Rewrites projected `SKILL.md` via `writing-for-agents` + `unslop` |",
            "| NVIDIA scorer | SkillEvaluator CLI | A | CLI internal / NIM | Static schema checks, rubric evaluation, package similarity |",
            f"| Actor | `llm.agents[]` | B | {agents} | Live conversational agent core across 1–2B, 8B, and 30B tiers |",
            f"| DeepEval judge | `llm.judge` | B | `{judge}` ({judge_channel}) | Evaluates task completion, tool correctness, and answer relevancy |",
            f"| Embeddings | `llm.embeddings` | train | `{embeddings}` | Rasano FAQ index compilation at `rasa train` (held fixed) |",
        ]
    )


def _judge_channel(provider: str) -> str:
    """Human label for the configured judge transport."""
    if provider == "openai":
        return "OpenAI API"
    if provider == "nvidia":
        return "NVIDIA NIM"
    return provider


def _tier_provider_label(actors: list[LlmEndpointSettings]) -> str:
    """Describe how a size-tier of actors is served."""
    providers = {actor.provider for actor in actors}
    if providers == {"local"}:
        return "Local GGUF via llama-server"
    if providers == {"nvidia"}:
        return "Cloud NIM Endpoints"
    return "mixed endpoints"


def _port_from_base_url(url: str | None) -> int | None:
    """Parse a TCP port from an actor base_url."""
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.port


def render_layer_b_actor_tiers(config: AppConfig) -> str:
    """Methodology bullets grouping configured actors by size tier and provider."""
    grouped: dict[str, list[LlmEndpointSettings]] = {}
    for actor in config.llm.agents:
        grouped.setdefault(model_size_tier(actor.path_id()), []).append(actor)
    lines: list[str] = []
    for tier in _TIER_ORDER:
        actors = grouped.get(tier) or []
        if not actors:
            continue
        lines.append(f"- **{tier} Tier ({_tier_provider_label(actors)})**:")
        for actor in actors:
            lines.append(f"  - `{actor.path_id()}` (`{actor.model}`)")
    leftover = [tier for tier in grouped if tier not in _TIER_ORDER]
    for tier in leftover:
        actors = grouped[tier]
        lines.append(f"- **{tier} Tier ({_tier_provider_label(actors)})**:")
        for actor in actors:
            lines.append(f"  - `{actor.path_id()}` (`{actor.model}`)")
    ports = sorted(
        {
            port
            for actor in config.llm.agents
            if actor.provider == "local"
            for port in (_port_from_base_url(actor.base_url),)
            if port is not None
        }
    )
    if ports:
        if len(ports) == 1:
            span = f"`:{ports[0]}`"
        else:
            span = f"`:{ports[0]}` to `:{ports[-1]}`"
        lines.append("")
        lines.append(
            f"Local models run one instance at a time on dedicated ports ({span}) "
            "to maintain bounded RAM usage."
        )
    return "\n".join(lines) if lines else "_No Layer B actors configured._"


def render_integration_issues(issues: list[IntegrationIssue]) -> str:
    """Markdown for Mantle/rasa-pro issues observed this run."""
    if not issues:
        return "_None this run._"
    blocks: list[str] = []
    for index, issue in enumerate(issues, 1):
        loc = "/".join(part for part in (issue.agent_id, issue.model_id, issue.arm) if part)
        heading = f"### {index}. `{issue.code}`"
        if loc:
            heading += f" at `{loc}`"
        lines = [heading, ""]
        lines.append(issue.message.strip() or "_no message_")
        lines.append("")
        if issue.workaround_applied:
            if issue.workaround_succeeded is True:
                status = "train recovered"
            elif issue.workaround_succeeded is False:
                status = "train still failed"
            else:
                status = "applied"
            lines.append(f"Workaround: {issue.workaround_applied} ({status}).")
            lines.append("")
        if issue.report_upstream:
            ask = issue.suggested_ask.strip() or "See the quoted engine message."
            lines.append(f"**Report this to Rasa.** {ask}")
            lines.append("")
        blocks.append("\n".join(lines).rstrip())
    return "\n\n".join(blocks) + "\n"


def unique_asks_for_rasa(issues: list[IntegrationIssue]) -> list[str]:
    """Deduplicate upstream asks from this run, preserving order."""
    seen: set[str] = set()
    asks: list[str] = []
    for issue in issues:
        if not issue.report_upstream:
            continue
        ask = issue.suggested_ask.strip()
        if not ask or ask in seen:
            continue
        seen.add(ask)
        asks.append(ask)
    return asks


def harness_notes_text(
    deltas: list[ImproverDelta],
    *,
    nvidia: list[NvidiaSkillResult] | None = None,
    deepeval: list[DeepEvalResult] | None = None,
    tsr: list[TsrRun] | None = None,
    interrupted: bool = False,
    pair_exclusions: dict[str, Any] | None = None,
    actors_completed: list[str] | None = None,
    actors_failed: list[str] | None = None,
    imported_from: str | None = None,
    kimi_skipped: bool = False,
) -> str:
    """Harness-only notes (not Mantle bugs): degraded improver, interrupt."""
    notes: list[str] = []
    nvidia_rows = nvidia or []
    incomplete_stages = sorted(
        {
            item.command
            for item in nvidia_rows
            if not nvidia_command_successful(item)
            and not any(
                other.command == item.command and nvidia_command_successful(other)
                for other in nvidia_rows
            )
        }
    )
    unavailable = sorted(
        {
            item.command
            for item in nvidia_rows
            if "unavailable" in (item.skip_reason or "").lower()
            or "end of life" in (item.skip_reason or "").lower()
            or "410" in (item.skip_reason or "")
        }
    )
    if unavailable:
        notes.append(
            "SkillEvaluator LLM/embedding unavailable for: "
            + ", ".join(f"`{name}`" for name in unavailable)
            + "."
        )
    judge_rows = deepeval or []
    scored_judge = any(item.score is not None and not item.skipped for item in judge_rows)
    attempted_judge = any(
        item.scenario_id != "*"
        or (
            "not installed" not in (item.skip_reason or "").lower()
            and "unavailable" not in (item.skip_reason or "").lower()
            and "no transcripts" not in (item.skip_reason or "").lower()
        )
        for item in judge_rows
    )
    if judge_rows:
        coverage_bits: list[str] = []
        planned = {
            (row.agent_id, row.model_id, row.arm, row.scenario_id, int(row.repeat))
            for row in (tsr or [])
            if not row.skipped
        }
        for metric_key in (
            "task_completion",
            "answer_relevancy",
            "tool_correctness",
            "g_eval_tool_correctness",
        ):
            metric_rows = [
                item
                for item in judge_rows
                if item.metric == metric_key and item.scenario_id != "*"
            ]
            if not metric_rows and not planned:
                continue
            scored_n = sum(
                1 for item in metric_rows if item.score is not None and not item.skipped
            )
            expected_n = len(planned) if planned else len(metric_rows)
            coverage_bits.append(f"`{metric_key}` {scored_n}/{expected_n}")
        if coverage_bits:
            notes.append("DeepEval coverage: " + ", ".join(coverage_bits) + ".")
        if not scored_judge:
            if attempted_judge and any(
                item.skip_reason and "not installed" not in item.skip_reason.lower()
                for item in judge_rows
            ):
                notes.append("DeepEval produced no scores (metric API errors).")
            else:
                incomplete_stages.append("deepeval")
    if incomplete_stages:
        notes.append(
            "Unexecuted evaluation stages: "
            + ", ".join(f"`{name}`" for name in sorted(set(incomplete_stages)))
            + "."
        )
    if interrupted:
        notes.append("Run interrupted; Layer B and DeepEval may be incomplete.")
    if actors_failed:
        notes.append(
            "Actors failed or skipped: "
            + ", ".join(f"`{name}`" for name in actors_failed)
            + "."
        )
    if actors_completed:
        notes.append(
            "Actors completed: "
            + ", ".join(f"`{name}`" for name in actors_completed)
            + "."
        )
    if pair_exclusions:
        native_only = int(pair_exclusions.get("native_only") or 0)
        improved_only = int(pair_exclusions.get("improved_only") or 0)
        skipped = int(pair_exclusions.get("skipped") or 0)
        if native_only or improved_only or skipped:
            notes.append(
                f"Paired TSR n={pair_exclusions.get('paired', 0)}; native-only {native_only}; "
                f"improved-only {improved_only}; skipped {skipped}."
            )
    heuristic_failed = [
        item.skill_id
        for item in deltas
        if item.mode in {"failed", "heuristic"}
    ]
    if heuristic_failed:
        notes.append(
            "Improver LLM failed for: "
            + ", ".join(f"`{name}`" for name in heuristic_failed)
            + ". Heuristic rewrite used; Layer A A/B is weaker for those skills."
        )
    degraded = [
        item.skill_id
        for item in deltas
        if item.degraded and item.skill_id not in heuristic_failed
    ]
    if degraded:
        notes.append(
            "Skills degraded (score below baseline or LLM failed after backup retry): "
            + ", ".join(f"`{name}`" for name in degraded)
            + "."
        )
    cached = [item.skill_id for item in deltas if item.mode == "cached"]
    if cached:
        notes.append(
            "Improver cache hit for: " + ", ".join(f"`{name}`" for name in cached) + "."
        )
    imported = [item.skill_id for item in deltas if item.mode == "imported"]
    if imported:
        notes.append(
            "Improver skipped (imported skills, Kimi not called) for: "
            + ", ".join(f"`{name}`" for name in imported)
            + "."
        )
    schema_hits = sorted(
        {
            item.skill_id
            for item in nvidia_rows
            if item.schema_high
        }
    )
    if schema_hits:
        notes.append(
            "NVIDIA SCHEMA HIGH on: "
            + ", ".join(f"`{name}`" for name in schema_hits)
            + ". NVIDIA-only Agent Skills demands that Mantle cannot consume "
            "stay in the projected copy (Report this to Rasa)."
        )
    if imported_from or kimi_skipped:
        source = imported_from or "donated Layer A packages"
        notes.append(
            f"Improver imported from `{source}`; Kimi was not called."
        )
    llm_n = sum(1 for item in deltas if item.mode == "llm")
    heur_n = sum(1 for item in deltas if item.mode == "heuristic")
    if llm_n and heur_n and not heuristic_failed:
        notes.append(f"Improver modes mixed: llm={llm_n}, heuristic={heur_n}, cached={len(cached)}.")
    return " ".join(notes) if notes else "none."


def render_run_inventory(
    config: AppConfig,
    inventories: list[MantleInventory],
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    issues: list[IntegrationIssue],
) -> str:
    """Heroes-style operational inventory for the appendix."""
    scope_counts = Counter(scope.value for inv in inventories for scope in inv.scopes)
    extra_keys = Counter(key for inv in inventories for key in inv.extra_frontmatter_keys)
    confirmations = sum(
        1 for inv in inventories if any(c.requires_confirmation for c in inv.tool_constraints)
    )
    cli = resolve_skillevaluator()
    lines = [
        "#### What we ran",
        "",
        f"- Engine pin: {config.project.engine} / rasa-pro {config.project.rasa_pro_version}",
        f"- Skills inventoried: {len(inventories)}",
        f"- SkillEvaluator CLI: {'yes' if cli else 'not installed'}",
        f"- Provider key: {'yes' if nvidia_key_configured() else 'no'}",
        f"- Improver rewrites: {len(deltas)}",
        f"- Actor models configured: {', '.join(a.path_id() for a in config.llm.agents) or 'none'}",
        f"- Actor models with live TSR: {', '.join(sorted({r.model_id for r in tsr if not r.skipped})) or 'none'}",
        "",
        "#### Scope mix",
        "",
    ]
    if scope_counts:
        for name, count in sorted(scope_counts.items()):
            lines.append(f"- `{name}`: {count}")
    else:
        lines.append("- _None._")
    lines.extend(
        [
            "",
            "#### Mantle-only inventory",
            "",
            f"- Skills with `requires_confirmation` on at least one tool: {confirmations}",
            "- Extra frontmatter keys that Agent Skills schema rejects:",
        ]
    )
    for key, count in extra_keys.most_common():
        lines.append(f"  - `{key}`: {count} skills")
    if not extra_keys:
        lines.append("  - none")
    high = [f for inv in inventories for f in inv.findings if f.severity.value == "high"]
    lines.extend(["", f"#### High Mantle-native findings, {len(high)}", ""])
    if high:
        for finding in high:
            lines.append(
                f"- `{finding.skill_id}` `{finding.code}`, {finding.finding_class.value}. {finding.message}"
            )
    else:
        lines.append("- None.")
    asks = [
        "Accept `SKILL.md` as an alias of `skill.md`.",
        "Kebab-case `name` matching the folder. Add `title:` for display names.",
        "Stamp `license` and `metadata.author` on official examples.",
        "Leave Mantle-only keys on the skill, or put them in `config/mantle.yml`.",
        *unique_asks_for_rasa(issues),
    ]
    lines.extend(["", "#### Asks for Rasa", ""])
    for ask in asks:
        lines.append(f"- {ask}")
    return "\n".join(lines)


def render_appendix_plots(config: AppConfig) -> str:
    """Links to plots omitted from the main-body visualization set."""
    lines = [
        "#### Layer A",
        "",
        "- [NVIDIA rubric delta](plots/rubric_delta.png)",
        "",
        "#### Layer B TSR",
        "",
        "- [NVIDIA vs strict TSR](plots/nvidia_vs_tsr_strict.png)",
    ]
    for actor in config.llm.agents:
        model_id = actor.path_id()
        lines.append(f"- [TSR {model_id}](plots/tsr_weighted_{model_id}.png)")
    lines.extend(
        [
            "",
            "#### DeepEval (LLM-as-a-judge)",
            "",
            "- [All metrics](plots/deepeval_by_metric.png)",
            "- [Task completion by model](plots/deepeval_by_model.png)",
            "- [Task completion by size](plots/deepeval_by_model_size.png)",
            "- [Task completion by scenario](plots/deepeval_by_scenario.png)",
            "- [Task completion by model (metric)](plots/deepeval_task_completion_by_model.png)",
            "- [Answer relevancy by model](plots/deepeval_answer_relevancy_by_model.png)",
            "- [Tool correctness by model](plots/deepeval_tool_correctness_by_model.png)",
            "- [GEval tool correctness by model](plots/deepeval_g_eval_tool_correctness_by_model.png)",
            "- [DeepEval vs TSR](plots/deepeval_vs_tsr.png)",
        ]
    )
    return "\n".join(lines)


def render_appendix(
    config: AppConfig,
    inventories: list[MantleInventory],
    nvidia: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
    stats: dict[str, Any],
    *,
    agent_models: str,
    agent_models_completed: str,
    improver_model: str,
    judge_model: str,
    embeddings_model: str,
    integration_issues: list[IntegrationIssue],
) -> str:
    """Low-level tables and plots from the previous short report, as an appendix."""
    sections = [
        "### Run coverage",
        "",
        f"- Improver: `{improver_model}`",
        f"- Actors (configured): {agent_models}",
        f"- Actors (completed): {agent_models_completed}",
        f"- Judge: `{judge_model}`",
        f"- Embeddings: `{embeddings_model}`",
        "",
        "### Extra DeepEval metrics",
        "",
        extra_deepeval_metrics_markdown(deepeval),
        "",
        "### Layer B by model (detail)",
        "",
        _layer_b_by_model_markdown(config, stats, deepeval, detail=True),
        "### Layer B total (equal-weight)",
        "",
        _layer_b_total(stats, intro=True),
        "",
        "### NVIDIA rubric criteria",
        "",
        render_rubric_criteria(nvidia),
        "",
        "### Additional plots",
        "",
        render_appendix_plots(config),
        "",
        improver_delta_markdown(deltas, heading="### Improver delta"),
        "",
        "### Run inventory",
        "",
        render_run_inventory(config, inventories, deltas, tsr, integration_issues),
    ]
    return "\n".join(sections)


def fill_report_template(
    template: str,
    values: dict[str, str],
) -> str:
    """Replace ``{{key}}`` placeholders. Unresolved keys become ``n/a``."""

    def repl(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return values[key]
        return "n/a"

    return _PLACEHOLDER.sub(repl, template)


def build_report_values(
    config: AppConfig,
    inventories: list[MantleInventory],
    nvidia: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
    stats: dict[str, Any],
    assessed_on: str | None = None,
    integration_issues: list[IntegrationIssue] | None = None,
    interrupted: bool = False,
    imported_from: str | None = None,
    kimi_skipped: bool = False,
) -> dict[str, str]:
    """Map template placeholders to filled strings."""
    stamp = assessed_on or datetime.now(UTC).strftime("%Y-%m-%d")
    q = stats.get("nvidia_quality") or {}
    tw = stats.get("tsr_weighted") or {}
    sp = stats.get("spearman_nvidia_vs_tsr") or {}
    agents = ", ".join(
        f"`{a.path_id()}` ({_endpoint_label(a.provider, a.model)})"
        for a in config.llm.agents
    ) or "n/a"
    completed_ids = sorted({r.model_id for r in tsr if not r.skipped})
    failed_ids = sorted(
        {r.model_id for r in tsr} - set(completed_ids)
    )
    observed = ", ".join(f"`{name}`" for name in completed_ids) or "none"
    issues = integration_issues or []
    improver_model = _endpoint_label(
        config.llm.improver.provider, config.llm.improver.model
    )
    judge_model = _endpoint_label(
        config.llm.judge.provider, config.llm.judge.model
    )
    embeddings_model = _endpoint_label(
        config.llm.embeddings.provider, config.llm.embeddings.model
    )
    corpora = _eval_corpora(config)
    return {
        "assessed_on": stamp,
        "rasa_pro_version": config.project.rasa_pro_version,
        "nvidia_quality.baseline": _fmt((q.get("baseline") or {}).get("mean"), 1),
        "nvidia_quality.improved": _fmt((q.get("improved") or {}).get("mean"), 1),
        "nvidia_quality.delta": _fmt(q.get("mean_delta"), 1),
        "nvidia_quality.p_value": _fmt(q.get("p_value")),
        "nvidia_quality.test": str(q.get("test") or "n/a"),
        "tsr_weighted.baseline": _fmt((tw.get("baseline") or {}).get("mean")),
        "tsr_weighted.improved": _fmt((tw.get("improved") or {}).get("mean")),
        "tsr_weighted.delta": _fmt(tw.get("mean_delta")),
        "tsr_weighted.p_value": _fmt(tw.get("p_value")),
        "tsr_weighted.test": str(tw.get("test") or "n/a"),
        "spearman.rho": _fmt(sp.get("rho")),
        "spearman.p_value": _fmt(sp.get("p_value")),
        "spearman.note": str(sp.get("note") or "n/a"),
        "nvidia.rubric_model": config.nvidia.rubric_model,
        "improver_model": improver_model,
        "improver_model_short": _model_short(config.llm.improver.model),
        "agent_models": agents,
        "agent_models_completed": observed,
        "judge_model": judge_model,
        "judge_provider": config.llm.judge.provider,
        "embeddings_model": embeddings_model,
        "model_roles_table": render_model_roles_table(config),
        "layer_b_actor_tiers": render_layer_b_actor_tiers(config),
        "metrics_table": render_metrics_markdown(
            nvidia, tsr, deepeval, deltas=deltas, corpora=corpora
        ),
        "layer_b_by_model": _layer_b_by_model_markdown(config, stats, deepeval, detail=False),
        "layer_b_total": _layer_b_total(stats, intro=False),
        "n_inventories": str(len(inventories)),
        "n_improver": str(len(deltas)),
        "integration_issues": render_integration_issues(issues),
        "harness_notes": harness_notes_text(
            deltas,
            nvidia=nvidia,
            deepeval=deepeval,
            tsr=tsr,
            interrupted=interrupted,
            pair_exclusions=stats.get("pair_exclusions") if isinstance(stats, dict) else None,
            actors_completed=completed_ids,
            actors_failed=failed_ids,
            imported_from=imported_from,
            kimi_skipped=kimi_skipped,
        ),
        "appendix": render_appendix(
            config,
            inventories,
            nvidia,
            deltas,
            tsr,
            deepeval,
            stats,
            agent_models=agents,
            agent_models_completed=observed,
            improver_model=improver_model,
            judge_model=judge_model,
            embeddings_model=embeddings_model,
            integration_issues=issues,
        ),
    }


def write_shareable_report(
    path: Path,
    config: AppConfig,
    inventories: list[MantleInventory],
    nvidia: list[NvidiaSkillResult],
    deltas: list[ImproverDelta],
    tsr: list[TsrRun],
    deepeval: list[DeepEvalResult],
    stats: dict[str, Any],
    assessed_on: str | None = None,
    plot_rel: str = "plots",
    template_path: Path | None = None,
    integration_issues: list[IntegrationIssue] | None = None,
    interrupted: bool = False,
    imported_from: str | None = None,
    kimi_skipped: bool = False,
) -> None:
    """Fill ``docs/REPORT.md`` template into a run-local REPORT.md."""
    tpl_path = template_path or (PROJECT_ROOT / "docs" / "REPORT.md")
    template = tpl_path.read_text(encoding="utf-8")
    values = build_report_values(
        config,
        inventories,
        nvidia,
        deltas,
        tsr,
        deepeval,
        stats,
        assessed_on=assessed_on,
        integration_issues=integration_issues,
        interrupted=interrupted,
        imported_from=imported_from,
        kimi_skipped=kimi_skipped,
    )
    filled = fill_report_template(template, values)
    # Run reports always link plots/ relative to the run folder.
    if plot_rel != "plots":
        filled = filled.replace("(plots/", f"({plot_rel}/")
    # Sanity: never leave raw skip logs from older generators.
    path.write_text(filled, encoding="utf-8")
