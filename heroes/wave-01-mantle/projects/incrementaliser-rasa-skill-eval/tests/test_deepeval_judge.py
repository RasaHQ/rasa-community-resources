"""DeepEval judging must use the configured ChatClient."""

from __future__ import annotations

import sys
import types
from pathlib import Path

from rasa_skill_eval.config import AppConfig, LlmEndpointSettings, LlmSettings, ProjectSettings
from rasa_skill_eval.deepeval_judge import _judge_label, _score_transcript, run_deepeval
from rasa_skill_eval.llm.types import ChatMessage, ChatResult
from rasa_skill_eval.models import TsrRun


def test_judge_label_uses_config() -> None:
    """Provenance strings include provider and model."""
    assert _judge_label(LlmEndpointSettings(provider="nvidia", model="x")) == "nvidia/x"
    settings = LlmEndpointSettings(
        provider="nvidia",
        model="nvidia/nemotron-3-super-120b-a12b",
    )
    assert _judge_label(settings) == "nvidia/nemotron-3-super-120b-a12b"


def test_run_deepeval_skips_without_package(monkeypatch, tmp_path: Path) -> None:
    """Missing deepeval extra is a skip, not a crash."""
    import builtins

    real_import = builtins.__import__

    def fake_import(name: str, *args: object, **kwargs: object):
        if name == "deepeval" or name.startswith("deepeval."):
            raise ImportError("no deepeval")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="judge")),
    )
    rows = run_deepeval(tmp_path, cfg, [])
    assert rows[0].skipped is True
    assert "deepeval" in (rows[0].skip_reason or "").lower()


def test_score_transcript_uses_configured_judge(monkeypatch, tmp_path: Path) -> None:
    """TaskCompletionMetric must receive the ChatClient adapter, not DeepEval's default."""
    captured: dict[str, str] = {}

    class FakeBase:
        """Stand-in for DeepEvalBaseLLM."""

    class FakeMetric:
        """Capture the model passed into TaskCompletionMetric."""

        def __init__(self, threshold: float = 0.5, model: object = None) -> None:
            del threshold
            self.model = model
            self.score = 0.9
            self.reason = "ok"

        def measure(self, case: object) -> None:
            del case
            assert self.model is not None
            captured["name"] = self.model.get_model_name()  # type: ignore[union-attr]
            captured["text"] = self.model.generate("grade this")  # type: ignore[union-attr]

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(
            self,
            input: str = "",
            actual_output: str = "",
            context: object = None,
            tools_called: object = None,
            expected_tools: object = None,
            **kwargs: object,
        ) -> None:
            del kwargs
            self.input = input
            self.actual_output = actual_output
            self.context = context
            self.tools_called = tools_called if tools_called is not None else []
            self.expected_tools = expected_tools if expected_tools is not None else []

    class FakeClient:
        """Chat client that records the judge prompt."""

        def complete(
            self,
            messages: list[ChatMessage],
            **kwargs: object,
        ) -> ChatResult:
            del kwargs
            captured["prompt"] = messages[0].content
            return ChatResult(text="judged")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = FakeBase
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text(
        '{"input": "hi", "output": "hello from the agent"}',
        encoding="utf-8",
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="judge-x")),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(
            scenario_id="faq",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            skill="banking_faq",
        ),
        cfg,
        FakeClient(),
    )
    assert captured["name"] == "nvidia/judge-x"
    assert captured["text"] == "judged"
    assert captured["prompt"] == "grade this"
    assert rows[0].judge_model == "nvidia/judge-x"
    assert rows[0].agent_id == "rasano"
    assert rows[0].score == 0.9


def test_score_transcript_multi_metrics(monkeypatch, tmp_path: Path) -> None:
    """TaskCompletion, AnswerRelevancy, and ToolCorrectness are all evaluated."""
    class FakeMetricBase:
        """Stand-in metric."""
        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = 0.85
            self.reason = "passed"

        def measure(self, case: object) -> None:
            del case

    class FakeCase:
        """Stand-in for LLMTestCase."""
        def __init__(
            self,
            input: str = "",
            actual_output: str = "",
            context: object = None,
            tools_called: object = None,
            expected_tools: object = None,
            **kwargs: object,
        ) -> None:
            del kwargs
            self.input = input
            self.actual_output = actual_output
            self.context = context
            self.tools_called = tools_called if tools_called is not None else []
            self.expected_tools = expected_tools if expected_tools is not None else []

    class FakeClient:
        """Chat client for judge."""
        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del kwargs, messages
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetricBase
    metrics.AnswerRelevancyMetric = FakeMetricBase

    class FakeToolMetric:
        """ToolCorrectnessMetric 2.9 rejects model=."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            if model is not None:
                raise TypeError("ToolCorrectnessMetric got an unexpected keyword argument 'model'")
            self.score = 0.85
            self.reason = "passed"

        def measure(self, case: object) -> None:
            del case

    class FakeGEval:
        """GEval is a separate metric, not a ToolCorrectness fallback."""

        def __init__(
            self,
            name: str = "",
            criteria: str = "",
            model: object = None,
            evaluation_params: object = None,
            **kwargs: object,
        ) -> None:
            del name, criteria, kwargs
            if evaluation_params is None:
                raise TypeError("GEval.__init__() missing 1 required argument: 'evaluation_params'")
            self.model = model
            self.score = 0.85
            self.reason = "passed"

        def measure(self, case: object) -> None:
            del case

    metrics.ToolCorrectnessMetric = FakeToolMetric
    metrics.GEval = FakeGEval
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object

    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text(
        '{"input": "check balance", "output": "your balance is 100"}',
        encoding="utf-8",
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="openai", model="gpt-4o")),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(
            scenario_id="balance_named",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="llama-8b",
            skill="check_balance",
        ),
        cfg,
        FakeClient(),
    )
    metric_names = [r.metric for r in rows]
    assert "task_completion" in metric_names
    assert "answer_relevancy" in metric_names
    assert "tool_correctness" in metric_names
    assert "g_eval_tool_correctness" in metric_names
    assert all(r.judge_model == "openai/gpt-4o" for r in rows)
    assert all(r.score == 0.85 for r in rows)


def test_format_judge_prompt_includes_comprehensive_context() -> None:
    """Judge prompt must contain scenario goals, expected tools, safety, and observations."""
    from rasa_skill_eval.deepeval_judge import format_judge_prompt

    row = TsrRun(
        scenario_id="transfer_confirmed",
        arm="native",
        repeat=0,
        agent_id="rasano",
        model_id="muse-30b",
        skill="transfer_money",
    )
    scenario = {
        "id": "transfer_confirmed",
        "description": "Customer transfers money and confirms.",
        "expect": {
            "skill_started": "transfer_money",
            "tools": ["process_transfer"],
            "safety_forbidden_tools": ["delete_account"],
            "confirmation": "required",
            "memory_set": {"amount": "50"},
        },
    }
    observation = {
        "skills_started": ["transfer_money"],
        "tools_called": ["process_transfer"],
        "tool_arguments": [{"name": "process_transfer", "amount": "50"}],
        "confirmation_seen": True,
    }
    prompt = format_judge_prompt("Send 50 dollars", row, scenario, observation)
    assert "Customer transfers money and confirms." in prompt
    assert "Target Skill: transfer_money" in prompt
    assert "Required Tools to Call: process_transfer" in prompt
    assert "Forbidden Tools (Safety Violations): delete_account" in prompt
    assert "User Confirmation Required: required" in prompt
    assert "Expected Memory / Slots Set: {'amount': '50'}" in prompt
    assert "Tools Actually Executed: process_transfer" in prompt
    assert "Confirmation Prompt Observed: Yes" in prompt


def test_coerce_schema_result_wraps_statements_string() -> None:
    """DeepEval schema objects receive a list even when the model returns a string."""
    from pydantic import BaseModel

    from rasa_skill_eval.deepeval_judge import _coerce_schema_result

    class Statements(BaseModel):
        """Minimal DeepEval-like schema."""

        statements: list[str]

    result = _coerce_schema_result(Statements, '{"statements": "the agent called the tool"}')
    assert result.statements == ["the agent called the tool"]


def test_score_transcript_records_per_metric_skip(monkeypatch, tmp_path: Path) -> None:
    """A failing metric becomes skipped=True, not a complete score."""

    class FakeMetric:
        """Always explode."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, model, kwargs

        def measure(self, case: object) -> None:
            del case
            raise RuntimeError("metric API mismatch")

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused judge."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="judge")),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
    )
    assert rows[0].skipped is True
    assert "metric API mismatch" in (rows[0].skip_reason or "")


def test_merge_deepeval_keeps_scores_and_fills_skips() -> None:
    """Resume must not overwrite a real score with a later skip."""
    from rasa_skill_eval.deepeval_judge import merge_deepeval_results
    from rasa_skill_eval.models import DeepEvalResult

    existing = [
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="task_completion",
            score=0.9,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="answer_relevancy",
            skipped=True,
            skip_reason="429",
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
    ]
    incoming = [
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="task_completion",
            skipped=True,
            skip_reason="should not win",
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
        DeepEvalResult(
            scenario_id="faq",
            arm="native",
            metric="answer_relevancy",
            score=0.4,
            agent_id="rasano",
            model_id="lfm-1.2b",
            repeat=0,
        ),
    ]
    merged = merge_deepeval_results(existing, incoming)
    by_metric = {row.metric: row for row in merged}
    assert by_metric["task_completion"].score == 0.9
    assert by_metric["task_completion"].skipped is False
    assert by_metric["answer_relevancy"].score == 0.4
    assert by_metric["answer_relevancy"].skipped is False


def test_score_transcript_switches_to_backup_judge(monkeypatch, tmp_path: Path) -> None:
    """Persistent 429/503 on the primary judge continues on the backup model."""
    from rasa_skill_eval.deepeval_judge import JudgeSession, _score_transcript

    class FakeMetric:
        """Fail on the primary judge name, succeed on backup."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = None
            self.reason = ""

        def measure(self, case: object) -> None:
            del case
            name = self.model.get_model_name() if self.model is not None else ""
            if "primary" in str(name):
                raise RuntimeError("HTTP 429 Too Many Requests")
            self.score = 0.61
            self.reason = "backup"

    class FakeGEval(FakeMetric):
        """Require evaluation_params like real GEval."""

        def __init__(
            self,
            name: str = "",
            criteria: str = "",
            model: object = None,
            evaluation_params: object = None,
            **kwargs: object,
        ) -> None:
            del name, criteria, kwargs
            if evaluation_params is None:
                raise TypeError("GEval.__init__() missing 1 required argument: 'evaluation_params'")
            super().__init__(model=model)

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused text client."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    metrics.GEval = FakeGEval
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(
            judge=LlmEndpointSettings(
                provider="nvidia",
                model="primary",
                backup_model="meta/llama-3.1-70b-instruct",
            )
        ),
    )
    session = JudgeSession(
        client=FakeClient(),
        settings=cfg.llm.judge,
        backup_client=FakeClient(),
        backup_settings=LlmEndpointSettings(provider="nvidia", model="backup"),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
        session=session,
        existing_ok={},
    )
    scored = [row for row in rows if row.score is not None and not row.skipped]
    assert scored
    assert all(row.judge_model == "nvidia/backup" for row in scored)
    assert session.using_backup is True


def test_score_transcript_retries_schema_then_backup(monkeypatch, tmp_path: Path) -> None:
    """GEval schema failures retry once, then switch to the backup judge."""
    from rasa_skill_eval.deepeval_judge import JudgeSession, _score_transcript

    calls = {"n": 0}

    class FakeMetric:
        """Fail with a schema error twice, then succeed on backup."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = None
            self.reason = ""

        def measure(self, case: object) -> None:
            del case
            calls["n"] += 1
            name = self.model.get_model_name() if self.model is not None else ""
            if "primary" in str(name):
                raise ValueError("judge output did not match schema: not json")
            self.score = 0.4
            self.reason = "backup schema ok"

    class FakeGEval(FakeMetric):
        """Require evaluation_params like real GEval."""

        def __init__(
            self,
            name: str = "",
            criteria: str = "",
            model: object = None,
            evaluation_params: object = None,
            **kwargs: object,
        ) -> None:
            del name, criteria, kwargs
            if evaluation_params is None:
                raise TypeError("GEval.__init__() missing 1 required argument: 'evaluation_params'")
            super().__init__(model=model)

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused text client."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    metrics.GEval = FakeGEval
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(
            judge=LlmEndpointSettings(
                provider="nvidia",
                model="primary",
                backup_model="meta/llama-3.1-70b-instruct",
            )
        ),
    )
    session = JudgeSession(
        client=FakeClient(),
        settings=cfg.llm.judge,
        backup_client=FakeClient(),
        backup_settings=LlmEndpointSettings(provider="nvidia", model="backup"),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
        session=session,
        existing_ok={},
    )
    scored = [row for row in rows if row.score is not None and not row.skipped]
    assert scored
    assert session.using_backup is True
    assert calls["n"] >= 3


def test_score_transcript_reuses_existing_metric_scores(monkeypatch, tmp_path: Path) -> None:
    """Per-metric resume skips metrics that already have a non-skipped score."""
    from rasa_skill_eval.models import DeepEvalResult

    measured: list[str] = []

    class FakeMetric:
        """Record constructions."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, model, kwargs
            measured.append("task")
            self.score = 0.11
            self.reason = "new"

        def measure(self, case: object) -> None:
            del case

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused judge."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="judge")),
    )
    prior = DeepEvalResult(
        scenario_id="faq",
        arm="native",
        metric="task_completion",
        score=0.88,
        agent_id="rasano",
        model_id="lfm-1.2b",
        repeat=0,
        judge_model="nvidia/judge",
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
        existing_ok={("rasano", "lfm-1.2b", "native", "faq", 0, "task_completion"): prior},
    )
    assert measured == []
    assert rows[0].score == 0.88


def test_coerce_schema_result_never_returns_bare_string() -> None:
    """When a schema is requested, a failed parse still yields a model instance."""
    from pydantic import BaseModel

    from rasa_skill_eval.deepeval_judge import _coerce_schema_result

    class Verdicts(BaseModel):
        """Schema with verdicts, matching DeepEval answer-relevancy objects."""

        statements: list[str] = []
        verdicts: list[str] = []

    result = _coerce_schema_result(Verdicts, "not json at all")
    assert not isinstance(result, str)
    assert result.statements == ["not json at all"]


def test_coerce_schema_result_accepts_geval_score_reason() -> None:
    """GEval often returns {score, reason} rather than statements."""
    from pydantic import BaseModel

    from rasa_skill_eval.deepeval_judge import _coerce_schema_result

    class ReasonScore(BaseModel):
        """GEval-like schema."""

        score: float
        reason: str

    result = _coerce_schema_result(
        ReasonScore, '{"score": 0, "reason": "no tools", "extra": true}'
    )
    assert result.score == 0.0
    assert "no tools" in result.reason


def test_score_transcript_keeps_retrying_rate_limits(monkeypatch, tmp_path: Path) -> None:
    """Backup 429s retry beyond three attempts instead of silently dropping the metric."""
    from rasa_skill_eval.config import EvalSettings
    from rasa_skill_eval.deepeval_judge import JudgeSession, _score_transcript

    calls = {"n": 0}

    class FakeMetric:
        """Fail with 429 four times, then score."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = None
            self.reason = ""

        def measure(self, case: object) -> None:
            del case
            calls["n"] += 1
            if calls["n"] < 5:
                raise RuntimeError("HTTP 429 Too Many Requests")
            self.score = 0.55
            self.reason = "waited"

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused text client."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        eval=EvalSettings(judge_max_retries=12),
        llm=LlmSettings(
            judge=LlmEndpointSettings(
                provider="nvidia",
                model="primary",
                backup_provider="openai",
                backup_model="gpt-4.1-mini",
            )
        ),
    )
    session = JudgeSession(
        client=FakeClient(),
        settings=cfg.llm.judge,
        backup_client=FakeClient(),
        backup_settings=LlmEndpointSettings(provider="openai", model="gpt-4.1-mini"),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
        session=session,
        existing_ok={},
    )
    scored = [row for row in rows if row.metric == "task_completion" and row.score is not None]
    assert scored
    assert scored[0].score == 0.55
    assert calls["n"] >= 5


def test_score_transcript_appends_skip_when_retries_exhausted(
    monkeypatch, tmp_path: Path
) -> None:
    """Exhausted rate-limit retries still write a skipped metric row."""
    from rasa_skill_eval.config import EvalSettings
    from rasa_skill_eval.deepeval_judge import JudgeSession, _score_transcript

    class FakeMetric:
        """Always 429."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = None

        def measure(self, case: object) -> None:
            del case
            raise RuntimeError("HTTP 429 Too Many Requests")

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Unused text client."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)

    transcript = tmp_path / "t.json"
    transcript.write_text('{"input": "hi", "output": "hello"}', encoding="utf-8")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        eval=EvalSettings(judge_max_retries=2),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="primary")),
    )
    session = JudgeSession(
        client=FakeClient(),
        settings=cfg.llm.judge,
        backup_client=FakeClient(),
        backup_settings=LlmEndpointSettings(provider="openai", model="gpt-4.1-mini"),
    )
    rows = _score_transcript(
        transcript,
        TsrRun(scenario_id="faq", arm="native", repeat=0, agent_id="rasano", model_id="lfm-1.2b"),
        cfg,
        FakeClient(),
        session=session,
        existing_ok={},
    )
    skipped = [row for row in rows if row.metric == "task_completion"]
    assert skipped
    assert skipped[0].skipped is True
    assert "429" in (skipped[0].skip_reason or "")


def test_run_deepeval_checkpoints_after_transcript(monkeypatch, tmp_path: Path) -> None:
    """A kill mid-matrix must not lose already-scored transcripts."""
    from rasa_skill_eval.deepeval_judge import run_deepeval
    from rasa_skill_eval.llm.types import ChatResult

    class FakeMetric:
        """Always score."""

        def __init__(self, threshold: float = 0.5, model: object = None, **kwargs: object) -> None:
            del threshold, kwargs
            self.model = model
            self.score = 0.7
            self.reason = "ok"

        def measure(self, case: object) -> None:
            del case

    class FakeCase:
        """Stand-in for LLMTestCase."""

        def __init__(self, **kwargs: object) -> None:
            del kwargs

    class FakeClient:
        """Judge client."""

        def complete(self, messages: list[ChatMessage], **kwargs: object) -> ChatResult:
            del messages, kwargs
            return ChatResult(text="ok")

    deepeval = types.ModuleType("deepeval")
    metrics = types.ModuleType("deepeval.metrics")
    metrics.TaskCompletionMetric = FakeMetric
    test_case = types.ModuleType("deepeval.test_case")
    test_case.LLMTestCase = FakeCase
    models = types.ModuleType("deepeval.models")
    base = types.ModuleType("deepeval.models.base_model")
    base.DeepEvalBaseLLM = object
    monkeypatch.setitem(sys.modules, "deepeval", deepeval)
    monkeypatch.setitem(sys.modules, "deepeval.metrics", metrics)
    monkeypatch.setitem(sys.modules, "deepeval.test_case", test_case)
    monkeypatch.setitem(sys.modules, "deepeval.models", models)
    monkeypatch.setitem(sys.modules, "deepeval.models.base_model", base)
    monkeypatch.setattr(
        "rasa_skill_eval.deepeval_judge.try_client", lambda *a, **k: FakeClient()
    )
    monkeypatch.setattr(
        "rasa_skill_eval.deepeval_judge.try_backup_client", lambda *a, **k: None
    )
    monkeypatch.setattr(
        "rasa_skill_eval.deepeval_judge.backup_endpoint", lambda *a, **k: None
    )

    tsr_dir = tmp_path / "tsr" / "transcripts" / "rasano" / "lfm-1.2b" / "native"
    tsr_dir.mkdir(parents=True)
    (tsr_dir / "faq__r0.json").write_text(
        '{"input": "hi", "output": "hello"}', encoding="utf-8"
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(judge=LlmEndpointSettings(provider="nvidia", model="judge")),
    )
    rows = run_deepeval(
        tmp_path,
        cfg,
        [
            TsrRun(
                scenario_id="faq",
                arm="native",
                repeat=0,
                agent_id="rasano",
                model_id="lfm-1.2b",
            )
        ],
    )
    saved = tmp_path / "deepeval" / "results.json"
    assert saved.is_file()
    assert any(row.score == 0.7 for row in rows)


