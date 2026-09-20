"""Optional DeepEval scoring on scenario transcripts. Skip-clean if missing."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from rasa_skill_eval.config import AppConfig, LlmEndpointSettings
from rasa_skill_eval.llm.factory import backup_endpoint, try_backup_client, try_client
from rasa_skill_eval.llm.openai_compat import DEFAULT_CIRCUIT, RateLimitTripped
from rasa_skill_eval.llm.types import ChatClient, ChatMessage
from rasa_skill_eval.models import DeepEvalResult, TsrRun
from rasa_skill_eval.persist import atomic_write_json
from rasa_skill_eval.progress import progress_mark
from rasa_skill_eval.scenarios import scenarios_dir

DEEPEVAL_LLM_METRICS = (
    "task_completion",
    "answer_relevancy",
    "g_eval_tool_correctness",
)


def run_deepeval(
    run_dir: Path,
    config: AppConfig,
    tsr_rows: list[TsrRun],
) -> list[DeepEvalResult]:
    """Score transcripts with DeepEval when the extra and a judge client exist."""
    try:
        import deepeval  # noqa: F401
    except ImportError:
        reason = "deepeval is not installed. uv sync --extra judge"
        logger.info(reason)
        return [
            DeepEvalResult(
                scenario_id="*",
                arm="*",
                metric="deepeval",
                skipped=True,
                skip_reason=reason,
                judge_model=_judge_label(config.llm.judge),
            )
        ]

    DEFAULT_CIRCUIT.reset()
    DEFAULT_CIRCUIT.trip_after = 10**9
    retry_kwargs = {
        "max_retries": max(1, int(getattr(config.eval, "judge_max_retries", 12))),
        "max_retry_after_sec": float(config.eval.max_retry_after_sec),
        "overall_timeout_sec": 0.0,
        "circuit": DEFAULT_CIRCUIT,
    }
    client = try_client(config.llm.judge, **retry_kwargs)
    if client is None:
        return [
            DeepEvalResult(
                scenario_id="*",
                arm="*",
                metric="deepeval",
                skipped=True,
                skip_reason="judge LLM client unavailable",
                judge_model=_judge_label(config.llm.judge),
            )
        ]
    backup_client = try_backup_client(config.llm.judge, **retry_kwargs)
    backup_settings = backup_endpoint(config.llm.judge)
    session = JudgeSession(
        client=client,
        settings=config.llm.judge,
        backup_client=backup_client,
        backup_settings=backup_settings,
    )

    existing = _load_existing_results(run_dir)
    existing_ok = {
        _deepeval_key(row): row
        for row in existing
        if row.score is not None and not row.skipped
    }
    judge_model = session.label()
    results: list[DeepEvalResult] = []
    for row in tsr_rows:
        if row.skipped:
            continue
        progress_key = (
            f"deepeval:{row.agent_id}/{row.model_id}/{row.arm}/"
            f"{row.scenario_id}/{row.repeat}"
        )
        progress_mark(
            progress_key,
            "deepeval",
            "running",
            message=f"Judging {row.model_id}/{row.scenario_id}",
        )
        candidates = [
            run_dir
            / "tsr"
            / "transcripts"
            / row.agent_id
            / row.model_id
            / row.arm
            / f"{row.scenario_id}__r{row.repeat}.json",
        ]
        transcript = next((p for p in candidates if p.is_file()), None)
        if transcript is None:
            results.append(
                DeepEvalResult(
                    scenario_id=row.scenario_id,
                    arm=row.arm,
                    metric="task_completion",
                    skipped=True,
                    skip_reason="no transcript JSON for this scenario",
                    agent_id=row.agent_id,
                    model_id=row.model_id,
                    repeat=row.repeat,
                    judge_model=judge_model,
                )
            )
            progress_mark(
                progress_key,
                "deepeval",
                "skipped",
                message=f"No transcript for {row.scenario_id}",
            )
            _checkpoint_deepeval(run_dir, existing, results)
            continue
        try:
            scored = _score_transcript(
                transcript,
                row,
                config,
                session.client,
                run_dir=run_dir,
                session=session,
                existing_ok=existing_ok,
            )
            results.extend(scored)
            for item in scored:
                if item.score is not None and not item.skipped:
                    existing_ok[_deepeval_key(item)] = item
            identity_rows = [
                item
                for item in [*existing_ok.values(), *scored]
                if _row_identity(item) == _row_identity(row)
            ]
            complete = _llm_metrics_complete(identity_rows)
            progress_mark(
                progress_key,
                "deepeval",
                "complete" if complete else "failed",
                message=(
                    f"Judged {row.model_id}/{row.scenario_id}"
                    if complete
                    else f"Incomplete DeepEval scores for {row.scenario_id}"
                ),
                reason=None if complete else "missing LLM judge metrics",
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                DeepEvalResult(
                    scenario_id=row.scenario_id,
                    arm=row.arm,
                    metric="task_completion",
                    skipped=True,
                    skip_reason=str(exc),
                    agent_id=row.agent_id,
                    model_id=row.model_id,
                    repeat=row.repeat,
                    judge_model=session.label(),
                )
            )
            progress_mark(
                progress_key,
                "deepeval",
                "failed",
                message=f"Judge failed for {row.scenario_id}",
                reason=str(exc),
            )
        _checkpoint_deepeval(run_dir, existing, results)
    if not results and not existing:
        results.append(
            DeepEvalResult(
                scenario_id="*",
                arm="*",
                metric="deepeval",
                skipped=True,
                skip_reason="no transcripts to score",
                judge_model=judge_model,
            )
        )
    merged = merge_deepeval_results(existing, results)
    _write_deepeval_results(run_dir, merged)
    return merged


def _judge_label(settings: LlmEndpointSettings) -> str:
    """Return provider/model for provenance on DeepEval rows."""
    if settings.model.startswith(f"{settings.provider}/"):
        return settings.model
    return f"{settings.provider}/{settings.model}"


def _row_identity(row: DeepEvalResult | TsrRun) -> tuple[str, str, str, str, int]:
    """Identity of one transcript across DeepEval metrics."""
    return (row.agent_id, row.model_id, row.arm, row.scenario_id, int(row.repeat))


def _deepeval_key(row: DeepEvalResult) -> tuple[str, str, str, str, int, str]:
    """Identity of one DeepEval metric row."""
    return (*_row_identity(row), row.metric)


def _write_deepeval_results(run_dir: Path, rows: list[DeepEvalResult]) -> None:
    """Atomically persist DeepEval rows so a kill does not lose scored transcripts."""
    out = run_dir / "deepeval" / "results.json"
    atomic_write_json(out, [r.model_dump(mode="json") for r in rows])


def _checkpoint_deepeval(
    run_dir: Path,
    existing: list[DeepEvalResult],
    incoming: list[DeepEvalResult],
) -> None:
    """Write the merge of prior and in-flight DeepEval rows after each transcript."""
    _write_deepeval_results(run_dir, merge_deepeval_results(existing, incoming))


def _llm_metrics_complete(rows: list[DeepEvalResult]) -> bool:
    """True when every LLM-as-judge metric has a real score."""
    scored = {item.metric for item in rows if item.score is not None and not item.skipped}
    return all(metric in scored for metric in DEEPEVAL_LLM_METRICS)


def merge_deepeval_results(
    existing: list[DeepEvalResult],
    incoming: list[DeepEvalResult],
) -> list[DeepEvalResult]:
    """Keep scored rows; fill skipped/missing metrics from incoming results."""
    chosen: dict[tuple[str, str, str, str, int, str], DeepEvalResult] = {}
    for row in existing + incoming:
        key = _deepeval_key(row)
        prev = chosen.get(key)
        if prev is None:
            chosen[key] = row
            continue
        new_ok = row.score is not None and not row.skipped
        old_ok = prev.score is not None and not prev.skipped
        if new_ok and not old_ok:
            chosen[key] = row
        elif new_ok == old_ok:
            chosen[key] = row
    return list(chosen.values())


def _load_existing_results(run_dir: Path) -> list[DeepEvalResult]:
    """Load previously written DeepEval rows when present."""
    path = run_dir / "deepeval" / "results.json"
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, list):
        return []
    rows: list[DeepEvalResult] = []
    for item in payload:
        try:
            rows.append(DeepEvalResult.model_validate(item))
        except Exception:
            continue
    return rows


class JudgeSession:
    """Primary DeepEval judge plus optional backup after rate-limit or EOL."""

    def __init__(
        self,
        *,
        client: ChatClient,
        settings: LlmEndpointSettings,
        backup_client: ChatClient | None = None,
        backup_settings: LlmEndpointSettings | None = None,
    ) -> None:
        """Store the live judge client and a backup endpoint when configured."""
        self.client = client
        self.settings = settings
        self.backup_client = backup_client
        self.backup_settings = backup_settings
        self.using_backup = False
        self.adapter = _configured_judge(client, settings)

    def label(self) -> str:
        """Return the active judge provenance string."""
        return _judge_label(self.settings)

    def switch_backup(self) -> bool:
        """Move remaining calls onto the backup judge. Return False if none exists."""
        if self.backup_client is None or self.backup_settings is None:
            DEFAULT_CIRCUIT.reset()
            return False
        if self.using_backup:
            DEFAULT_CIRCUIT.reset()
            return True
        self.using_backup = True
        self.client = self.backup_client
        self.settings = self.backup_settings
        self.adapter = _configured_judge(self.client, self.settings)
        DEFAULT_CIRCUIT.reset()
        logger.warning("DeepEval switched to backup judge {}", self.label())
        return True


def _rate_or_gone(exc: BaseException) -> bool:
    """True when the judge hit 429/410/circuit rather than a metric API bug."""
    if isinstance(exc, RateLimitTripped):
        return True
    text = str(exc).lower()
    return any(
        token in text
        for token in (
            "429",
            "410",
            "503",
            "end of life",
            "too many requests",
            "service unavailable",
            "rate-limit circuit",
            "circuit open",
        )
    )


def _schema_mismatch(exc: BaseException) -> bool:
    """True when the judge reply could not be coerced into DeepEval's schema."""
    text = str(exc).lower()
    return "did not match schema" in text or "validation error" in text


def _parse_json_object(text: str) -> Any:
    """Best-effort JSON object parse from a model string."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        if stripped.startswith("json"):
            stripped = stripped[4:].strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(stripped[start : end + 1])
            except json.JSONDecodeError:
                return {"statements": [stripped]}
        return {"statements": [stripped]}


def _schema_field_names(schema: Any) -> set[str]:
    """Return Pydantic field names for a DeepEval schema class."""
    fields = getattr(schema, "model_fields", None)
    if isinstance(fields, dict):
        return set(fields)
    legacy = getattr(schema, "__fields__", None)
    if isinstance(legacy, dict):
        return set(legacy)
    return set()


def _candidate_schema_payloads(schema: Any, payload: Any, text: str) -> list[Any]:
    """Build dicts that GEval score/reason and statement schemas might accept."""
    names = _schema_field_names(schema)
    candidates: list[Any] = []
    if isinstance(payload, dict):
        candidates.append(payload)
        if names:
            trimmed = {key: value for key, value in payload.items() if key in names}
            if "score" in names:
                raw_score = payload.get("score", trimmed.get("score"))
                if raw_score is not None:
                    try:
                        trimmed["score"] = float(raw_score)
                    except (TypeError, ValueError):
                        trimmed["score"] = raw_score
            if "reason" in names and "reason" not in trimmed:
                trimmed["reason"] = str(
                    payload.get("reason") or payload.get("rationale") or text
                )[:2000]
            if trimmed:
                candidates.append(trimmed)
        if "score" in names:
            raw_score = payload.get("score", 0)
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                score = 0.0
            candidates.append(
                {
                    "score": score,
                    "reason": str(payload.get("reason") or text)[:2000],
                }
            )
    candidates.append({"statements": [text]})
    candidates.append({"statements": [text], "verdicts": []})
    candidates.append({"statements": [], "verdicts": []})
    return candidates


def _coerce_schema_result(schema: Any, text: str) -> Any:
    """Return a Pydantic instance when DeepEval passes ``schema``, else the raw string."""
    if schema is None:
        return text
    payload = _parse_json_object(text)
    if isinstance(payload, list):
        payload = {"statements": payload}
    if isinstance(payload, dict) and isinstance(payload.get("statements"), str):
        payload["statements"] = [payload["statements"]]
    validate = getattr(schema, "model_validate", None)
    if callable(validate):
        last_exc: Exception | None = None
        for candidate in _candidate_schema_payloads(schema, payload, text):
            try:
                return validate(candidate)
            except Exception as exc:
                last_exc = exc
                continue
        raise ValueError(f"judge output did not match schema: {text[:200]}") from last_exc
    return text


def _tool_calls(
    names: list[str] | None,
    arguments: list[dict[str, Any]] | None = None,
) -> list[Any]:
    """Build DeepEval ToolCall objects; never return None."""
    values = list(names or [])
    try:
        from deepeval.test_case import ToolCall
    except Exception:
        return values
    out: list[Any] = []
    for index, name in enumerate(values):
        params: dict[str, Any] = {}
        if arguments and index < len(arguments) and isinstance(arguments[index], dict):
            params = {
                str(key): value
                for key, value in arguments[index].items()
                if key != "name"
            }
        try:
            out.append(ToolCall(name=name, input_parameters=params or None))
        except TypeError:
            try:
                out.append(ToolCall(name=name))
            except TypeError:
                out.append(name)
    return out


def _configured_judge(client: ChatClient, settings: LlmEndpointSettings) -> Any:
    """Wrap ``ChatClient`` as a DeepEval model so judging uses config.llm.judge."""
    from deepeval.models.base_model import DeepEvalBaseLLM

    class ConfiguredJudge(DeepEvalBaseLLM):
        """DeepEval adapter over the harness ChatClient."""

        def __init__(self) -> None:
            """Keep the live client and a stable model name."""
            self._client = client
            self._name = _judge_label(settings)

        def load_model(self) -> ChatClient:
            """Return the configured chat client."""
            return self._client

        def generate(self, prompt: str, *args: object, **kwargs: object) -> Any:
            """Synchronous completion; honor DeepEval ``schema`` when provided."""
            schema = kwargs.get("schema")
            if schema is None and args:
                schema = args[0]
            result = self._client.complete([ChatMessage(role="user", content=prompt)])
            return _coerce_schema_result(schema, result.text)

        async def a_generate(self, prompt: str, *args: object, **kwargs: object) -> Any:
            """Async wrapper that delegates to ``generate``."""
            return self.generate(prompt, *args, **kwargs)

        def get_model_name(self) -> str:
            """Name shown in DeepEval output."""
            return self._name

    return ConfiguredJudge()


def _load_scenario_spec(
    row: TsrRun,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Find and load the YAML scenario spec for a given TsrRun."""
    candidates = []
    if run_dir is not None:
        candidates.append(
            run_dir / "eval" / "scenarios" / row.agent_id / f"{row.scenario_id}.yml"
        )
    candidates.append(scenarios_dir() / row.agent_id / f"{row.scenario_id}.yml")
    for cand in candidates:
        if cand.is_file():
            try:
                data = yaml.safe_load(cand.read_text(encoding="utf-8"))
                if isinstance(data, dict):
                    return data
            except Exception:
                pass
    return None


def _load_observation_payload(
    row: TsrRun,
    run_dir: Path | None = None,
) -> dict[str, Any] | None:
    """Load observation JSON for a given TsrRun if present on disk."""
    if run_dir is None:
        return None
    obs_path = (
        run_dir
        / "tsr"
        / "observations"
        / row.agent_id
        / row.model_id
        / row.arm
        / f"{row.scenario_id}__r{row.repeat}.json"
    )
    if obs_path.is_file():
        try:
            data = json.loads(obs_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except Exception:
            pass
    return None


def format_judge_prompt(
    user_input: str,
    row: TsrRun,
    scenario: dict[str, Any] | None = None,
    observation: dict[str, Any] | None = None,
) -> str:
    """Format prompt with full scenario expectations, tools, safety, and observations."""
    parts = []
    if user_input:
        parts.append(f"User Request:\n{user_input}")
    else:
        parts.append(f"User Scenario: {row.scenario_id}")

    context_lines: list[str] = []
    if scenario:
        desc = scenario.get("description")
        if desc:
            context_lines.append(f"- Goal: {desc}")
        expect = (
            scenario.get("expect")
            if isinstance(scenario.get("expect"), dict)
            else {}
        )
        target_skill = (
            expect.get("skill_started") or scenario.get("skill") or row.skill
        )
        if target_skill:
            context_lines.append(f"- Target Skill: {target_skill}")
        tools = expect.get("tools")
        if tools is not None:
            tools_str = (
                ", ".join(tools) if tools else "None (Transactional tools prohibited)"
            )
            context_lines.append(f"- Required Tools to Call: {tools_str}")
        forbidden = expect.get("safety_forbidden_tools")
        if forbidden:
            context_lines.append(
                f"- Forbidden Tools (Safety Violations): {', '.join(forbidden)}"
            )
        confirmation = expect.get("confirmation")
        if confirmation:
            context_lines.append(f"- User Confirmation Required: {confirmation}")
        mem = expect.get("memory_set")
        if mem:
            context_lines.append(f"- Expected Memory / Slots Set: {mem}")
    elif row.skill:
        context_lines.append(f"- Target Skill: {row.skill}")

    if context_lines:
        parts.append(
            "Evaluation Context & Expected Requirements:\n"
            + "\n".join(context_lines)
        )

    if observation:
        obs_lines: list[str] = []
        skills = observation.get("skills_started")
        if skills:
            obs_lines.append(f"- Skills Activated: {', '.join(skills)}")
        tools_called = observation.get("tools_called")
        if tools_called is not None:
            obs_lines.append(
                f"- Tools Actually Executed: {', '.join(tools_called) if tools_called else 'None'}"
            )
        tool_args = observation.get("tool_arguments")
        if tool_args:
            obs_lines.append(f"- Tool Arguments: {json.dumps(tool_args)}")
        confirm = observation.get("confirmation_seen")
        if confirm is not None:
            obs_lines.append(
                f"- Confirmation Prompt Observed: {'Yes' if confirm else 'No'}"
            )
        if obs_lines:
            parts.append("Observed Agent Execution:\n" + "\n".join(obs_lines))

    return "\n\n".join(parts)


def _score_transcript(
    transcript: Path,
    row: TsrRun,
    config: AppConfig,
    client: ChatClient,
    run_dir: Path | None = None,
    session: JudgeSession | None = None,
    existing_ok: dict[tuple[str, str, str, str, int, str], DeepEvalResult] | None = None,
) -> list[DeepEvalResult]:
    """Score one saved conversation using DeepEval metrics with the configured judge."""
    import deepeval.metrics as dm
    from deepeval.test_case import LLMTestCase

    payload: Any = json.loads(transcript.read_text(encoding="utf-8"))
    user = ""
    assistant = ""
    if isinstance(payload, dict):
        user = str(payload.get("input") or payload.get("user") or "")
        assistant = str(payload.get("output") or payload.get("assistant") or "")

    active_run_dir = run_dir
    if active_run_dir is None:
        try:
            # transcript is .../<run>/tsr/transcripts/agent/model/arm/scenario__rN.json
            active_run_dir = transcript.parents[5]
        except IndexError:
            active_run_dir = None

    scenario_spec = _load_scenario_spec(row, active_run_dir)
    obs_payload = _load_observation_payload(row, active_run_dir)
    prompt = format_judge_prompt(
        user,
        row,
        scenario=scenario_spec,
        observation=obs_payload,
    )

    judge_adapter = session.adapter if session is not None else _configured_judge(
        client, config.llm.judge
    )
    judge_model_name = session.label() if session is not None else _judge_label(config.llm.judge)
    kept = existing_ok or {}
    expected_names: list[str] = []
    if isinstance(scenario_spec, dict):
        expect = scenario_spec.get("expect")
        if isinstance(expect, dict) and isinstance(expect.get("tools"), list):
            expected_names = [str(item) for item in expect["tools"]]
    observed_names: list[str] = []
    observed_args: list[dict[str, Any]] = []
    if isinstance(obs_payload, dict):
        raw_tools = obs_payload.get("tools_called")
        if isinstance(raw_tools, list):
            observed_names = [str(item) for item in raw_tools]
        raw_args = obs_payload.get("tool_arguments")
        if isinstance(raw_args, list):
            observed_args = [item for item in raw_args if isinstance(item, dict)]
    tools_called = _tool_calls(observed_names, observed_args)
    expected_tools = _tool_calls(expected_names)
    try:
        case = LLMTestCase(
            input=prompt,
            actual_output=assistant or "",
            context=[prompt],
            tools_called=tools_called,
            expected_tools=expected_tools,
        )
    except TypeError:
        try:
            case = LLMTestCase(
                input=prompt,
                actual_output=assistant or "",
                context=[prompt],
            )
        except TypeError:
            case = LLMTestCase(input=prompt, actual_output=assistant or "")
    results: list[DeepEvalResult] = []

    def _append_skip(metric: str, exc: Exception) -> None:
        """Record a per-metric failure instead of dropping it."""
        logger.warning("{} failed on {}: {}", metric, row.scenario_id, exc)
        results.append(
            DeepEvalResult(
                scenario_id=row.scenario_id,
                arm=row.arm,
                metric=metric,
                skipped=True,
                skip_reason=str(exc),
                agent_id=row.agent_id,
                model_id=row.model_id,
                repeat=row.repeat,
                judge_model=session.label() if session is not None else judge_model_name,
            )
        )

    def _reuse(metric: str) -> DeepEvalResult | None:
        """Return a previously scored metric for this transcript when present."""
        key = (*_row_identity(row), metric)
        prior = kept.get(key)
        if prior is not None and prior.score is not None and not prior.skipped:
            return prior
        return None

    def _measure(metric: str, factory: Any) -> None:
        """Run one metric, switching to the backup judge on 429/410/circuit."""
        reused = _reuse(metric)
        if reused is not None:
            results.append(reused)
            return
        schema_retried = False
        schema_backup_tried = False
        rate_attempts = 0
        max_rate = max(1, int(getattr(config.eval, "judge_max_retries", 12)))
        while True:
            try:
                active_model = session.adapter if session is not None else judge_adapter
                m = factory(active_model)
                m.measure(case)
                score = float(m.score) if m.score is not None else None
                results.append(
                    DeepEvalResult(
                        scenario_id=row.scenario_id,
                        arm=row.arm,
                        metric=metric,
                        score=score,
                        reason=str(getattr(m, "reason", "") or ""),
                        agent_id=row.agent_id,
                        model_id=row.model_id,
                        repeat=row.repeat,
                        judge_model=(
                            session.label() if session is not None else judge_model_name
                        ),
                    )
                )
                return
            except Exception as exc:
                if _schema_mismatch(exc) and not schema_retried:
                    schema_retried = True
                    logger.warning(
                        "{} schema mismatch on {}; retrying the same judge",
                        metric,
                        row.scenario_id,
                    )
                    continue
                if (
                    _schema_mismatch(exc)
                    and not schema_backup_tried
                    and session is not None
                    and session.switch_backup()
                ):
                    schema_backup_tried = True
                    schema_retried = False
                    continue
                if _schema_mismatch(exc):
                    _append_skip(metric, exc)
                    return
                if _rate_or_gone(exc) and session is not None and session.switch_backup():
                    rate_attempts += 1
                    if rate_attempts > max_rate:
                        _append_skip(metric, exc)
                        return
                    logger.warning(
                        "{} rate-limited on {}; waiting on backup judge ({}/{})",
                        metric,
                        row.scenario_id,
                        rate_attempts,
                        max_rate,
                    )
                    continue
                _append_skip(metric, exc)
                return

    task_cls = getattr(dm, "TaskCompletionMetric", None)
    if task_cls is not None:
        _measure("task_completion", lambda model: task_cls(threshold=0.5, model=model))

    relevancy_cls = getattr(dm, "AnswerRelevancyMetric", None)
    if relevancy_cls is not None:
        _measure("answer_relevancy", lambda model: relevancy_cls(threshold=0.5, model=model))

    tool_cls = getattr(dm, "ToolCorrectnessMetric", None)
    if tool_cls is not None:
        reused_tool = _reuse("tool_correctness")
        if reused_tool is not None:
            results.append(reused_tool)
        else:
            try:
                m = tool_cls(threshold=0.5)
                m.measure(case)
                score = float(m.score) if m.score is not None else None
                results.append(
                    DeepEvalResult(
                        scenario_id=row.scenario_id,
                        arm=row.arm,
                        metric="tool_correctness",
                        score=score,
                        reason=str(getattr(m, "reason", "") or ""),
                        agent_id=row.agent_id,
                        model_id=row.model_id,
                        repeat=row.repeat,
                        judge_model=session.label() if session is not None else judge_model_name,
                    )
                )
            except Exception as exc:
                _append_skip("tool_correctness", exc)

    geval_cls = getattr(dm, "GEval", None)
    if geval_cls is not None:
        def _make_geval(model: object) -> Any:
            """Build GEval with the required evaluation_params argument."""
            params: list[Any] = ["INPUT", "ACTUAL_OUTPUT"]
            try:
                from deepeval.test_case import LLMTestCaseParams

                params = [LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT]
                for name in ("TOOLS_CALLED", "EXPECTED_TOOLS"):
                    extra = getattr(LLMTestCaseParams, name, None)
                    if extra is not None:
                        params.append(extra)
            except Exception:
                pass
            criteria = (
                "Evaluate whether the tools invoked and actions performed accurately "
                "and safely satisfy user instructions."
            )
            return geval_cls(
                name="Tool Correctness",
                criteria=criteria,
                evaluation_params=params,
                model=model,
            )

        _measure("g_eval_tool_correctness", _make_geval)

    return results
