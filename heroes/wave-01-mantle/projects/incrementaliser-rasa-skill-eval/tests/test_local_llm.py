"""Local llama-server helpers used by Layer B."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rasa_skill_eval.config import LlmEndpointSettings
from rasa_skill_eval.local_llm import (
    LlamaLaunchOptions,
    is_local_provider,
    pids_listening,
    port_from_base_url,
    spec_for,
    wait_ready,
)


def test_port_from_base_url_reads_explicit_port() -> None:
    """Actor base_url ports must drive llama-server --port."""
    assert port_from_base_url("http://127.0.0.1:8082/v1") == 8082
    assert port_from_base_url("http://127.0.0.1/v1") == 8081


def test_spec_for_matches_id_and_alias() -> None:
    """Catalog lookup uses config id, then llama-server alias."""
    by_id = spec_for(LlmEndpointSettings(id="lfm-1.2b", provider="local", model="x"))
    assert by_id is not None
    assert by_id.filename.startswith("LFM2-1.2B")
    by_alias = spec_for(
        LlmEndpointSettings(provider="local", model="llama-3.1-8b-instruct")
    )
    assert by_alias is not None
    assert "8B-Instruct" in by_alias.filename


def test_nvidia_is_not_local() -> None:
    """NIM actors must not spawn llama-server."""
    assert not is_local_provider("nvidia")
    assert is_local_provider("local")


class _DeadProc:
    """Process that has already exited."""

    returncode = 1

    def poll(self) -> int:
        """Exited."""
        return 1


def test_wait_ready_fails_on_wall_clock_jump() -> None:
    """Host sleep must expire the startup budget even if monotonic barely moves."""
    calls = {"n": 0}

    def wall() -> float:
        calls["n"] += 1
        return 0.0 if calls["n"] == 1 else 400.0

    mono_values = iter([0.0, 1.0, 2.0])

    def mono() -> float:
        return next(mono_values, 2.0)

    assert wait_ready(
        "http://127.0.0.1:9/v1",
        timeout_sec=300.0,
        monotonic_fn=mono,
        wall_fn=wall,
        sleep_fn=lambda _s: None,
        models_fn=lambda _url: [],
        heartbeat_sec=0.0,
    ) is False


def test_wait_ready_fails_when_process_exits() -> None:
    """A llama-server that dies during load is not waited out."""
    assert wait_ready(
        "http://127.0.0.1:9/v1",
        timeout_sec=300.0,
        proc=_DeadProc(),  # type: ignore[arg-type]
        sleep_fn=lambda _s: None,
        models_fn=lambda _url: [],
        heartbeat_sec=0.0,
    ) is False


def test_start_llama_kills_tree_when_not_ready(monkeypatch, tmp_path: Path) -> None:
    """A hung llama-server is killed and dropped from ownership on startup timeout."""
    from rasa_skill_eval.local_llm import _OWNED, _start_llama, spec_for

    exe = tmp_path / "llama-server.exe"
    exe.write_text("x", encoding="utf-8")
    gguf = tmp_path / "weights.gguf"
    gguf.write_text("x", encoding="utf-8")
    settings = LlmEndpointSettings(
        id="lfm-1.2b",
        provider="local",
        model="LFM2-1.2B",
        base_url="http://127.0.0.1:19999/v1",
    )
    killed = {"n": 0}

    class _Alive:
        """Process that never becomes ready."""

        pid = 4242

        def poll(self) -> int | None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 1

        def kill(self) -> None:
            return None

        def terminate(self) -> None:
            return None

    monkeypatch.setattr("rasa_skill_eval.local_llm.llama_server_exe", lambda: exe)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.local_base_url",
        lambda _s: "http://127.0.0.1:19999/v1",
    )
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.subprocess.Popen",
        lambda *a, **k: _Alive(),
    )
    monkeypatch.setattr("rasa_skill_eval.local_llm.wait_ready", lambda *a, **k: False)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.kill_process_tree",
        lambda _p: killed.__setitem__("n", killed["n"] + 1),
    )
    monkeypatch.setattr("rasa_skill_eval.local_llm.is_port_open", lambda *_a, **_k: False)
    monkeypatch.setattr("rasa_skill_eval.local_llm.flash_attn_supported", lambda _exe: False)
    spec = spec_for(settings)
    assert spec is not None
    try:
        with pytest.raises(TimeoutError):
            _start_llama(settings, spec, gguf, timeout_sec=1, log_dir=tmp_path / "logs")
    finally:
        _OWNED.pop(19999, None)
    assert killed["n"] == 1
    assert 19999 not in _OWNED


def test_ensure_local_actor_restarts_wrong_external_model(monkeypatch, tmp_path: Path) -> None:
    """A listener on the actor port serving a different alias is stopped, then replaced."""
    from rasa_skill_eval.local_llm import OwnedLlama, ensure_local_actor

    settings = LlmEndpointSettings(
        id="lfm-1.2b",
        provider="local",
        model="LFM2-1.2B",
        base_url="http://127.0.0.1:18082/v1",
    )
    stopped: list[int] = []
    started = {"n": 0}

    class _Proc:
        pid = 7

        def poll(self) -> int | None:
            return None

    fake = OwnedLlama(proc=_Proc(), port=18082, alias="LFM2-1.2B", exe="x")  # type: ignore[arg-type]
    monkeypatch.setattr("rasa_skill_eval.local_llm.owned_llama", lambda _p: None)
    monkeypatch.setattr("rasa_skill_eval.local_llm.is_port_open", lambda *_a, **_k: True)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm._server_model_ids", lambda _u: ["other-model"]
    )
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.stop_port",
        lambda port, **_k: stopped.append(port),
    )
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.ensure_gguf", lambda _s: tmp_path / "m.gguf"
    )
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm._start_llama",
        lambda *_a, **_k: started.__setitem__("n", 1) or fake,
    )
    out = ensure_local_actor(settings, [settings])
    assert stopped == [18082]
    assert started["n"] == 1
    assert out is fake


def test_ensure_local_actor_keeps_matching_external_listener(monkeypatch, tmp_path: Path) -> None:
    """A healthy listener already serving the alias is left alone."""
    from rasa_skill_eval.local_llm import ensure_local_actor

    settings = LlmEndpointSettings(
        id="lfm-1.2b",
        provider="local",
        model="LFM2-1.2B",
        base_url="http://127.0.0.1:18082/v1",
    )
    monkeypatch.setattr("rasa_skill_eval.local_llm.owned_llama", lambda _p: None)
    monkeypatch.setattr("rasa_skill_eval.local_llm.is_port_open", lambda *_a, **_k: True)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm._server_model_ids", lambda _u: ["LFM2-1.2B"]
    )

    def boom(*_a: object, **_k: object) -> None:
        raise AssertionError("must not restart a matching listener")

    monkeypatch.setattr("rasa_skill_eval.local_llm.stop_port", boom)
    monkeypatch.setattr("rasa_skill_eval.local_llm._start_llama", boom)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.ensure_gguf", lambda _s: tmp_path / "m.gguf"
    )
    assert ensure_local_actor(settings, [settings]) is None


def test_spec_for_resolves_30b_local_actors() -> None:
    """muse-30b and gemma4-31b have Q4_K_M catalog rows and 8k context."""
    muse = spec_for(LlmEndpointSettings(id="muse-30b", provider="local", model="x"))
    gemma = spec_for(LlmEndpointSettings(id="gemma4-31b", provider="local", model="x"))
    assert muse is not None
    assert muse.alias == "muse-glimmer-30b"
    assert muse.filename == "Muse-Glimmer-30B-Q4_K_M.gguf"
    assert muse.context == 8192
    assert gemma is not None
    assert gemma.alias == "gemma-4-31b-it"
    assert gemma.filename == "google_gemma-4-31B-it-Q4_K_M.gguf"
    assert gemma.context == 8192
    lfm = spec_for(LlmEndpointSettings(id="lfm-1.2b", provider="local", model="LFM2-1.2B"))
    assert lfm is not None
    assert lfm.context == 8192


def test_start_llama_argv_includes_gpu_flags(monkeypatch, tmp_path: Path) -> None:
    """CUDA launch passes -ngl 99 and -fa on when flash-attn is enabled."""
    from rasa_skill_eval.local_llm import _OWNED, _start_llama, spec_for

    exe = tmp_path / "llama-server"
    exe.write_text("x", encoding="utf-8")
    gguf = tmp_path / "weights.gguf"
    gguf.write_text("x", encoding="utf-8")
    settings = LlmEndpointSettings(
        id="llama-8b",
        provider="local",
        model="llama-3.1-8b-instruct",
        base_url="http://127.0.0.1:18083/v1",
    )
    captured: dict[str, list[str]] = {}

    class _Alive:
        """Process that never becomes ready."""

        pid = 9

        def poll(self) -> int | None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 1

        def kill(self) -> None:
            return None

        def terminate(self) -> None:
            return None

    def fake_popen(args: list[str], **_kwargs: object) -> _Alive:
        captured["args"] = list(args)
        return _Alive()

    monkeypatch.setattr("rasa_skill_eval.local_llm.llama_server_exe", lambda: exe)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.local_base_url",
        lambda _s: "http://127.0.0.1:18083/v1",
    )
    monkeypatch.setattr("rasa_skill_eval.local_llm.subprocess.Popen", fake_popen)
    monkeypatch.setattr("rasa_skill_eval.local_llm.wait_ready", lambda *a, **k: False)
    monkeypatch.setattr("rasa_skill_eval.local_llm.kill_process_tree", lambda _p: None)
    monkeypatch.setattr("rasa_skill_eval.local_llm.is_port_open", lambda *_a, **_k: False)
    monkeypatch.setattr("rasa_skill_eval.local_llm.flash_attn_supported", lambda _exe: True)
    spec = spec_for(settings)
    assert spec is not None
    try:
        with pytest.raises(TimeoutError):
            _start_llama(
                settings,
                spec,
                gguf,
                timeout_sec=1,
                options=LlamaLaunchOptions(
                    n_gpu_layers=99,
                    flash_attn=True,
                    parallel=1,
                    threads=8,
                ),
            )
    finally:
        _OWNED.pop(18083, None)
    args = captured["args"]
    assert args[args.index("-ngl") + 1] == "99"
    assert args[args.index("-fa") + 1] == "on"
    assert args[args.index("-c") + 1] == "8192"
    assert args[args.index("--parallel") + 1] == "1"


def test_start_llama_omits_gpu_offload_when_layers_zero(
    monkeypatch, tmp_path: Path
) -> None:
    """n_gpu_layers 0 is CPU-only: no -ngl and no -fa."""
    from rasa_skill_eval.local_llm import _OWNED, _start_llama, spec_for

    exe = tmp_path / "llama-server"
    exe.write_text("x", encoding="utf-8")
    gguf = tmp_path / "weights.gguf"
    gguf.write_text("x", encoding="utf-8")
    settings = LlmEndpointSettings(
        id="llama-8b",
        provider="local",
        model="llama-3.1-8b-instruct",
        base_url="http://127.0.0.1:18083/v1",
    )
    captured: dict[str, list[str]] = {}

    class _Alive:
        """Process that never becomes ready."""

        pid = 9

        def poll(self) -> int | None:
            return None

        def wait(self, timeout: float | None = None) -> int:
            del timeout
            return 1

        def kill(self) -> None:
            return None

        def terminate(self) -> None:
            return None

    def fake_popen(args: list[str], **_kwargs: object) -> _Alive:
        captured["args"] = list(args)
        return _Alive()

    monkeypatch.setattr("rasa_skill_eval.local_llm.llama_server_exe", lambda: exe)
    monkeypatch.setattr(
        "rasa_skill_eval.local_llm.local_base_url",
        lambda _s: "http://127.0.0.1:18083/v1",
    )
    monkeypatch.setattr("rasa_skill_eval.local_llm.subprocess.Popen", fake_popen)
    monkeypatch.setattr("rasa_skill_eval.local_llm.wait_ready", lambda *a, **k: False)
    monkeypatch.setattr("rasa_skill_eval.local_llm.kill_process_tree", lambda _p: None)
    monkeypatch.setattr("rasa_skill_eval.local_llm.is_port_open", lambda *_a, **_k: False)
    monkeypatch.setattr("rasa_skill_eval.local_llm.flash_attn_supported", lambda _exe: True)
    spec = spec_for(settings)
    assert spec is not None
    try:
        with pytest.raises(TimeoutError):
            _start_llama(
                settings,
                spec,
                gguf,
                timeout_sec=1,
                options=LlamaLaunchOptions(
                    n_gpu_layers=0,
                    flash_attn=False,
                    parallel=1,
                    threads=8,
                ),
            )
    finally:
        _OWNED.pop(18083, None)
    args = captured["args"]
    assert "-ngl" not in args
    assert "-fa" not in args


def test_pids_listening_linux_parses_ss(monkeypatch) -> None:
    """Linux listener recovery uses ss -ltnp, not Windows netstat."""
    monkeypatch.setattr("rasa_skill_eval.local_llm.sys.platform", "linux")

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[:2] == ["ss", "-ltnp"]:
            stdout = (
                'LISTEN 0 4096 127.0.0.1:8085 0.0.0.0:* '
                'users:(("llama-server",pid=4242,fd=6))\n'
            )
            return subprocess.CompletedProcess(cmd, 0, stdout, "")
        raise AssertionError(f"unexpected command {cmd}")

    monkeypatch.setattr("rasa_skill_eval.local_llm.subprocess.run", fake_run)
    assert pids_listening(8085) == [4242]


def test_pids_listening_linux_falls_back_to_lsof(monkeypatch) -> None:
    """Empty ss output falls back to lsof PIDs."""
    monkeypatch.setattr("rasa_skill_eval.local_llm.sys.platform", "linux")

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if cmd[:1] == ["ss"]:
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[:1] == ["lsof"]:
            return subprocess.CompletedProcess(cmd, 0, "99\n", "")
        raise AssertionError(f"unexpected command {cmd}")

    monkeypatch.setattr("rasa_skill_eval.local_llm.subprocess.run", fake_run)
    assert pids_listening(8086) == [99]


def test_pids_listening_windows_parses_netstat(monkeypatch) -> None:
    """Windows listener recovery still uses netstat -ano."""
    monkeypatch.setattr("rasa_skill_eval.local_llm.sys.platform", "win32")

    def fake_run(cmd: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        assert cmd[0] == "netstat"
        stdout = "  TCP    127.0.0.1:8083         0.0.0.0:0    LISTENING       4321\n"
        return subprocess.CompletedProcess(cmd, 0, stdout, "")

    monkeypatch.setattr("rasa_skill_eval.local_llm.subprocess.run", fake_run)
    assert pids_listening(8083) == [4321]
