"""Train-log parsing, Layer B progress logs, and observe-then-workaround retraining."""

from __future__ import annotations

import json
from pathlib import Path

from pytest import MonkeyPatch

from rasa_skill_eval.agent_eval import (
    _load_observed_fixture,
    _train_agent,
    _try_sync,
    format_arm_label,
    format_live_eval_start,
    format_live_scenario_progress,
    layer_b_eval_hash,
    parse_train_issues,
    run_agent_eval,
    run_arm,
    successful_arm_count,
)
from rasa_skill_eval.config import (
    AppConfig,
    EvalSettings,
    LlmEndpointSettings,
    LlmSettings,
    ProjectSettings,
)
from rasa_skill_eval.models import ObservedTrace, TsrRun
from rasa_skill_eval.persist import save_coverage, set_coverage_unit
from rasa_skill_eval.proc import CommandTimeout
from rasa_skill_eval.remerge import AGENT_SKILLS_HEADING_ASK, SESSION_PROSE_ASK, UNKNOWN_STEP_ASK


def test_parse_train_issues_session_prose() -> None:
    """Mantle validate_project session-prose JSON becomes an upstream issue."""
    log = json.dumps(
        {
            "event_msg": (
                "'session.check_balance.account_number' in instruction prose. "
                "'session.*' belongs in 'if:' conditions and structured fields; "
                "it is not substituted in free prose."
            ),
            "finding_count": 2,
            "event": "mantle.validate_project.project_validation_error",
            "level": "error",
        }
    )
    issues = parse_train_issues(log, agent_id="rasano", model_id="lfm-1.2b", arm="improved")
    assert issues
    assert issues[0].code == "memory.session_in_prose"
    assert issues[0].report_upstream is True
    assert issues[0].suggested_ask == SESSION_PROSE_ASK
    assert issues[0].event == "mantle.validate_project.project_validation_error"


def test_parse_train_issues_agent_skills_headings() -> None:
    """Heading rejection on reverse-merged skill.md is reported upstream."""
    log = "validate_project failed: unexpected heading '## Instructions' in skill.md"
    issues = parse_train_issues(log, agent_id="rasano", model_id="lfm-1.2b", arm="improved")
    assert issues[0].code == "mantle.agent_skills_headings"
    assert issues[0].report_upstream is True
    assert issues[0].suggested_ask == AGENT_SKILLS_HEADING_ASK


def test_parse_train_issues_unknown_step_property() -> None:
    """Unknown ``done_when`` on an ExecuteStep is a reverse-merge issue."""
    log = (
        "Skill directory 'skills/default_session_start' failed to load and would "
        "be silently skipped: Unknown step property 'done_when' on step 'load_profile'."
    )
    issues = parse_train_issues(log, agent_id="rasano", model_id="lfm-1.2b", arm="improved")
    assert issues[0].code == "mantle.unknown_step_property"
    assert issues[0].report_upstream is True
    assert issues[0].suggested_ask == UNKNOWN_STEP_ASK


def test_train_agent_retrains_after_unknown_step(tmp_path: Path, monkeypatch) -> None:
    """First train failure on ``done_when`` can recover after stripping keys."""
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._rasa_ready", lambda _root: (True, "ok")
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._try_sync", lambda _root, *a, **k: (True, "ok")
    )
    calls = {"n": 0}

    def fake_train(_root: Path, *args: object, **kwargs: object) -> tuple[bool, str]:
        del args, kwargs
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "Unknown step property 'done_when' on step 'load_profile'."
        return True, "trained"

    monkeypatch.setattr("rasa_skill_eval.agent_eval._try_rasa_train", fake_train)
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.apply_unknown_step_workaround",
        lambda _root: 2,
    )
    trained, reason, issues = _train_agent(
        tmp_path, agent_id="rasano", model_id="lfm-1.2b", arm="improved"
    )
    assert trained is True
    assert "unknown-step" in reason
    assert calls["n"] == 2
    assert issues[0].workaround_applied is not None
    assert issues[0].workaround_succeeded is True


def test_train_agent_retrains_after_session_prose(tmp_path: Path, monkeypatch) -> None:
    """First train failure is recorded; workaround + second train can recover."""
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._rasa_ready", lambda _root: (True, "ok")
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._try_sync", lambda _root, *a, **k: (True, "ok")
    )
    calls = {"n": 0}

    def fake_train(_root: Path, *args: object, **kwargs: object) -> tuple[bool, str]:
        del args, kwargs
        calls["n"] += 1
        if calls["n"] == 1:
            return False, "'session.check_balance.account_number' in instruction prose."
        return True, "trained"

    monkeypatch.setattr("rasa_skill_eval.agent_eval._try_rasa_train", fake_train)
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.apply_session_prose_workaround",
        lambda _root: 2,
    )
    trained, reason, issues = _train_agent(
        tmp_path, agent_id="rasano", model_id="lfm-1.2b", arm="improved"
    )
    assert trained is True
    assert "workaround" in reason
    assert calls["n"] == 2
    assert issues[0].workaround_applied is not None
    assert issues[0].workaround_succeeded is True
    assert issues[0].report_upstream is True


def test_format_live_scenario_progress_is_one_based() -> None:
    """Stdout uses 1-based repeats so humans can match the plan example."""
    assert format_arm_label("rasano", "lfm-2.6b", "improved") == "rasano/lfm-2.6b/improved"
    assert format_live_eval_start("rasano", "lfm-2.6b", "improved", 8, 3) == (
        "Live eval rasano/lfm-2.6b/improved: 8 scenarios × 3 repeats"
    )
    assert format_live_scenario_progress(
        "rasano", "lfm-2.6b", "improved", "faq_grounded", 0, 3
    ) == "rasano/lfm-2.6b/improved faq_grounded repeat 1/3"


def _info_lines(monkeypatch: MonkeyPatch, target: str) -> list[str]:
    """Capture loguru-style ``logger.info(fmt, *args)`` as formatted strings."""
    lines: list[str] = []

    def fake_info(message: str, *args: object, **kwargs: object) -> None:
        del kwargs
        lines.append(str(message).format(*args) if args else str(message))

    monkeypatch.setattr(target, fake_info)
    return lines


def test_train_agent_logs_start_and_trained(tmp_path: Path, monkeypatch) -> None:
    """uv sync and rasa train can take minutes; log before and after."""
    lines = _info_lines(monkeypatch, "rasa_skill_eval.agent_eval.logger.info")
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._rasa_ready", lambda _root: (True, "ok")
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._try_sync", lambda _root, *a, **k: (True, "ok")
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._try_rasa_train", lambda _root, *a, **k: (True, "trained")
    )
    trained, _reason, _issues = _train_agent(
        tmp_path, agent_id="rasano", model_id="lfm-2.6b", arm="improved"
    )
    assert trained is True
    assert "Training rasano/lfm-2.6b/improved" in lines
    assert "Trained rasano/lfm-2.6b/improved" in lines


def test_run_arm_logs_each_scenario_repeat(tmp_path: Path, monkeypatch) -> None:
    """Live eval must log start and latency so stdout is not silent after API ready."""
    scenario_dir = tmp_path / "eval" / "scenarios" / "rasano"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "faq_grounded.yml").write_text(
        "id: faq_grounded\nagent: rasano\nturns:\n  - user: hi\nexpect: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._train_agent",
        lambda *_a, **_k: (True, "trained", []),
    )

    class _FakeServer:
        """Stand-in that never binds a port."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def healthy(self) -> bool:
            return True

        def restart(self) -> None:
            return None

    monkeypatch.setattr("rasa_skill_eval.agent_eval.RasaRestServer", _FakeServer)
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.run_scenario_live",
        lambda _server, _spec: ObservedTrace(bot_text="ok", latency_sec=12.3),
    )
    lines = _info_lines(monkeypatch, "rasa_skill_eval.agent_eval.logger.info")
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        eval=EvalSettings(repeats=2),
    )
    rows, issues = run_arm(
        tmp_path,
        "improved",
        cfg,
        tmp_path,
        agent_id="rasano",
        model_id="lfm-2.6b",
    )
    assert issues == []
    assert len(rows) == 2
    assert "Live eval rasano/lfm-2.6b/improved: 1 scenarios × 2 repeats" in lines
    assert "Live rasano/lfm-2.6b/improved faq_grounded repeat 1/2" in lines
    assert "Done rasano/lfm-2.6b/improved faq_grounded repeat 1/2 latency=12.3s" in lines
    assert "Live rasano/lfm-2.6b/improved faq_grounded repeat 2/2" in lines
    assert "Done rasano/lfm-2.6b/improved faq_grounded repeat 2/2 latency=12.3s" in lines


def test_run_arm_opens_circuit_and_restarts_unhealthy_server(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """Consecutive timeouts restart Rasa and skip the rest of the arm."""
    scenario_dir = tmp_path / "eval" / "scenarios" / "rasano"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "faq_grounded.yml").write_text(
        "id: faq_grounded\nagent: rasano\nturns:\n  - user: hi\nexpect: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._train_agent",
        lambda *_a, **_k: (True, "trained", []),
    )
    restarts = {"n": 0}

    class _FakeServer:
        """Server that looks wedged after a timeout."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def healthy(self) -> bool:
            return False

        def restart(self) -> None:
            restarts["n"] += 1

    monkeypatch.setattr("rasa_skill_eval.agent_eval.RasaRestServer", _FakeServer)
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.run_scenario_live",
        lambda *_a, **_k: (_ for _ in ()).throw(TimeoutError("scenario timed out")),
    )
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        eval=EvalSettings(repeats=3, consecutive_timeout_limit=2),
    )
    rows, _issues = run_arm(
        tmp_path,
        "native",
        cfg,
        tmp_path,
        agent_id="rasano",
        model_id="lfm-1.2b",
    )
    assert len(rows) == 3
    assert rows[0].skipped is True
    assert rows[1].skipped is True
    assert "circuit breaker" in (rows[2].skip_reason or "")
    assert restarts["n"] >= 1


def test_run_arm_skips_completed_repeats(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Resume must not rerun a scenario repeat that already scored."""
    scenario_dir = tmp_path / "eval" / "scenarios" / "rasano"
    scenario_dir.mkdir(parents=True)
    (scenario_dir / "faq_grounded.yml").write_text(
        "id: faq_grounded\nagent: rasano\nturns:\n  - user: hi\nexpect: {}\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._train_agent",
        lambda *_a, **_k: (True, "trained", []),
    )
    live_calls = {"n": 0}

    class _FakeServer:
        """Stand-in that never binds a port."""

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            return None

        def start(self) -> None:
            return None

        def stop(self) -> None:
            return None

        def healthy(self) -> bool:
            return True

        def restart(self) -> None:
            return None

    def fake_live(_server: object, _spec: object) -> ObservedTrace:
        live_calls["n"] += 1
        return ObservedTrace(bot_text="ok", latency_sec=1.0)

    monkeypatch.setattr("rasa_skill_eval.agent_eval.RasaRestServer", _FakeServer)
    monkeypatch.setattr("rasa_skill_eval.agent_eval.run_scenario_live", fake_live)
    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        eval=EvalSettings(repeats=2),
    )
    existing = [
        TsrRun(
            scenario_id="faq_grounded",
            arm="native",
            repeat=0,
            agent_id="rasano",
            model_id="lfm-1.2b",
            weighted=1.0,
        )
    ]
    rows, _issues = run_arm(
        tmp_path,
        "native",
        cfg,
        tmp_path,
        agent_id="rasano",
        model_id="lfm-1.2b",
        existing_rows=existing,
    )
    assert live_calls["n"] == 1
    assert len(rows) == 1
    assert rows[0].repeat == 1


def test_successful_arm_count_excludes_skipped_placeholders() -> None:
    """Coverage completion counts scored repeats, not timeout placeholders."""
    rows = [
        TsrRun(
            scenario_id="faq_grounded",
            arm="native",
            repeat=repeat,
            agent_id="rasano",
            model_id="gemma4-31b",
            skipped=repeat > 0,
        )
        for repeat in range(3)
    ]
    assert successful_arm_count(
        rows,
        agent_id="rasano",
        model_id="gemma4-31b",
        arm="native",
    ) == 1


def test_load_observed_fixture_requires_exact_path(tmp_path: Path) -> None:
    """Generic observation files must not score a different agent/model/arm."""
    generic = tmp_path / "tsr" / "observations" / "faq_grounded.json"
    generic.parent.mkdir(parents=True)
    generic.write_text(
        ObservedTrace(bot_text="generic").model_dump_json(),
        encoding="utf-8",
    )
    exact = (
        tmp_path
        / "tsr"
        / "observations"
        / "rasano"
        / "lfm-1.2b"
        / "native"
        / "faq_grounded.json"
    )
    exact.parent.mkdir(parents=True)
    exact.write_text(
        ObservedTrace(bot_text="exact").model_dump_json(),
        encoding="utf-8",
    )
    hit = _load_observed_fixture(
        tmp_path, "native", "faq_grounded", agent_id="rasano", model_id="lfm-1.2b"
    )
    assert hit is not None
    assert hit.bot_text == "exact"
    miss = _load_observed_fixture(
        tmp_path, "native", "faq_grounded", agent_id="rasano", model_id="other"
    )
    assert miss is None


def test_try_sync_timeout_is_a_failure(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    """uv sync CommandTimeout becomes (False, reason), not an uncaught error."""
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.run_captured",
        lambda *_a, **_k: (_ for _ in ()).throw(CommandTimeout("uv timed out")),
    )
    ok, reason = _try_sync(tmp_path, timeout_sec=1)
    assert ok is False
    assert "timed out" in reason


def test_train_agent_reuses_fingerprint_cache(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A matching train fingerprint copies models and skips rasa train."""
    agent_root = tmp_path / "agent"
    models = agent_root / "models"
    models.mkdir(parents=True)
    (models / "model.tar.gz").write_text("weights", encoding="utf-8")
    cache = tmp_path / "train-cache"
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._rasa_ready", lambda _root: (True, "ok")
    )
    trains = {"n": 0}

    def fake_train(_root: Path, *args: object, **kwargs: object) -> tuple[bool, str]:
        del args, kwargs
        trains["n"] += 1
        return True, "trained"

    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval._try_sync", lambda _root, *a, **k: (True, "ok")
    )
    monkeypatch.setattr("rasa_skill_eval.agent_eval._try_rasa_train", fake_train)
    first, reason, _issues = _train_agent(
        agent_root,
        agent_id="rasano",
        model_id="lfm-1.2b",
        arm="native",
        train_cache_dir=cache,
    )
    assert first is True
    assert trains["n"] == 1
    dest = tmp_path / "agent2"
    dest.mkdir()
    second, reason2, _ = _train_agent(
        dest,
        agent_id="rasano",
        model_id="lfm-1.2b",
        arm="native",
        train_cache_dir=cache,
    )
    assert second is True
    assert "cache" in reason2
    assert trains["n"] == 1
    assert (dest / "models" / "model.tar.gz").is_file()


def test_run_agent_eval_skips_complete_actor(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    """A coverage-complete actor is not started again on --run-dir resume."""
    from rasa_skill_eval.agent_eval import _copy_scenarios

    cfg = AppConfig(
        project=ProjectSettings(rasa_pro_version="3.20.0.dev6", engine="mantle"),
        llm=LlmSettings(
            agents=[LlmEndpointSettings(id="tiny", provider="nvidia", model="x")]
        ),
        eval=EvalSettings(repeats=1),
        corpora={},
    )
    dest = tmp_path / "run"
    dest.mkdir()
    _copy_scenarios(dest, cfg)
    coverage: dict[str, object] = {
        "units": {},
        "eval_hash": layer_b_eval_hash(cfg, dest / "eval" / "scenarios"),
    }
    set_coverage_unit(
        coverage, "actor:tiny", status="complete", kind="actor", model_id="tiny"
    )
    save_coverage(dest, coverage)
    monkeypatch.setattr(
        "rasa_skill_eval.agent_eval.ensure_local_actor",
        lambda *_a, **_k: (_ for _ in ()).throw(AssertionError("actor should be skipped")),
    )
    monkeypatch.setattr("rasa_skill_eval.agent_eval.stop_local_actors", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "rasa_skill_eval.deepeval_judge.run_deepeval",
        lambda *_a, **_k: [],
    )
    run_agent_eval(config=cfg, run_dir=dest)
