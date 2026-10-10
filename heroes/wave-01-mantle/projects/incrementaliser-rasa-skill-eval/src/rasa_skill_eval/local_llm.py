"""Start and stop local llama-server actors used by Layer B.

Only one GGUF stays loaded at a time so 8B CPU weights do not sit beside LFM.
This module owns the child process: logs are kept, timeouts kill the tree, and
port discovery is only a fallback for leftover listeners.
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, TextIO
from urllib.parse import urlparse

import httpx
from dotenv import load_dotenv
from loguru import logger

from rasa_skill_eval import PROJECT_ROOT
from rasa_skill_eval.config import EvalSettings, LlmEndpointSettings, load_config
from rasa_skill_eval.proc import Deadline, kill_process_tree

MODELS_DIR = PROJECT_ROOT / "models"
DEFAULT_LLAMA_SERVER = Path(
    r"C:\ArashMath\AutoJob\llama.cpp\build\bin\Release\llama-server.exe"
)
DEFAULT_LOCAL_BASE = "http://127.0.0.1:8081/v1"
_LOCAL_PROVIDERS = frozenset({"local", "llama", "llamacpp", "llama.cpp"})
_CREATE_NO_WINDOW = 0x08000000
_OWNED: dict[int, OwnedLlama] = {}


@dataclass
class OwnedLlama:
    """llama-server child started by this process."""

    proc: subprocess.Popen[str]
    port: int
    alias: str
    exe: str
    log_path: Path | None = None
    log_file: TextIO | None = field(default=None, repr=False)


@dataclass(frozen=True)
class LlamaLaunchOptions:
    """CPU/GPU knobs passed to llama-server (YAML plus env override)."""

    n_gpu_layers: int = 99
    flash_attn: bool = True
    parallel: int = 1
    threads: int = 8


@dataclass(frozen=True)
class GgufSpec:
    """Hugging Face GGUF plus llama-server alias and context length."""

    repo_id: str
    filename: str
    alias: str
    context: int = 8192


GGUF_SPECS: dict[str, GgufSpec] = {
    "lfm-1.2b": GgufSpec(
        repo_id="LiquidAI/LFM2-1.2B-GGUF",
        filename="LFM2-1.2B-Q4_K_M.gguf",
        alias="LFM2-1.2B",
        context=8192,
    ),
    "lfm-2.6b": GgufSpec(
        repo_id="LiquidAI/LFM2-2.6B-GGUF",
        filename="LFM2-2.6B-Q4_K_M.gguf",
        alias="LFM2-2.6B",
        context=8192,
    ),
    "llama-8b": GgufSpec(
        repo_id="bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
        filename="Meta-Llama-3.1-8B-Instruct-Q4_K_M.gguf",
        alias="llama-3.1-8b-instruct",
        context=8192,
    ),
    "nemotron-8b": GgufSpec(
        repo_id="bartowski/nvidia_Llama-3.1-Nemotron-Nano-8B-v1-GGUF",
        filename="nvidia_Llama-3.1-Nemotron-Nano-8B-v1-Q4_K_M.gguf",
        alias="llama-3.1-nemotron-nano-8b-v1",
        context=8192,
    ),
    "muse-30b": GgufSpec(
        repo_id="bartowski/Muse-Glimmer-30B-GGUF",
        filename="Muse-Glimmer-30B-Q4_K_M.gguf",
        alias="muse-glimmer-30b",
        context=8192,
    ),
    "gemma4-31b": GgufSpec(
        repo_id="bartowski/google_gemma-4-31B-it-GGUF",
        filename="google_gemma-4-31B-it-Q4_K_M.gguf",
        alias="gemma-4-31b-it",
        context=8192,
    ),
}


def is_local_provider(provider: str) -> bool:
    """Return True when this endpoint is served by llama.cpp."""
    return provider.strip().lower() in _LOCAL_PROVIDERS


def local_base_url(settings: LlmEndpointSettings) -> str:
    """Resolve the OpenAI-compatible base URL for a local actor."""
    load_dotenv(PROJECT_ROOT / ".env")
    return (
        (settings.base_url or os.getenv("LLAMA_BASE_URL") or DEFAULT_LOCAL_BASE).rstrip("/")
    )


def port_from_base_url(base_url: str, default: int = 8081) -> int:
    """Parse the listen port from an OpenAI-compatible base URL."""
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    if parsed.port:
        return int(parsed.port)
    if parsed.scheme == "https":
        return 443
    return default


def spec_for(settings: LlmEndpointSettings) -> GgufSpec | None:
    """Look up the GGUF row for a local actor id or alias."""
    key = (settings.id or "").strip()
    if key in GGUF_SPECS:
        return GGUF_SPECS[key]
    model = (settings.model or "").strip()
    for spec in GGUF_SPECS.values():
        if spec.alias == model:
            return spec
    return None


def llama_launch_options(eval_settings: EvalSettings | None = None) -> LlamaLaunchOptions:
    """Read llama-server knobs from ``eval`` YAML, with ``LLAMA_N_GPU_LAYERS`` override."""
    load_dotenv(PROJECT_ROOT / ".env")
    settings = eval_settings
    if settings is None:
        try:
            settings = load_config().eval
        except Exception:
            settings = EvalSettings()
    n_gpu = int(settings.llama_n_gpu_layers)
    raw = os.getenv("LLAMA_N_GPU_LAYERS", "").strip()
    if raw:
        n_gpu = int(raw)
    return LlamaLaunchOptions(
        n_gpu_layers=n_gpu,
        flash_attn=bool(settings.llama_flash_attn),
        parallel=max(1, int(settings.llama_parallel)),
        threads=max(1, int(settings.llama_threads)),
    )


def flash_attn_supported(exe: Path) -> bool:
    """Return True when this binary documents ``-fa`` / ``--flash-attn``."""
    try:
        proc = subprocess.run(
            [str(exe), "-h"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    blob = f"{proc.stdout}\n{proc.stderr}".lower()
    return "--flash-attn" in blob or "\n-fa" in blob or " -fa " in blob


def llama_server_exe() -> Path:
    """Resolve llama-server: ``LLAMA_SERVER_EXE``, PATH, then Windows AutoJob fallback."""
    load_dotenv(PROJECT_ROOT / ".env")
    raw = os.getenv("LLAMA_SERVER_EXE", "").strip()
    if raw:
        return Path(raw)
    found = shutil.which("llama-server")
    if found:
        return Path(found)
    if sys.platform == "win32":
        return DEFAULT_LLAMA_SERVER
    return Path("llama-server")


def gguf_path(spec: GgufSpec) -> Path:
    """Return the on-disk GGUF path under ``models/``."""
    return MODELS_DIR / spec.filename


def download_gguf(model_id: str, dest_dir: Path | None = None) -> Path:
    """Fetch one Q4_K_M GGUF. Returns the local file path."""
    spec = GGUF_SPECS.get(model_id)
    if spec is None:
        raise KeyError(f"Unknown local model id {model_id}")
    try:
        from huggingface_hub import hf_hub_download
    except ImportError as exc:
        raise RuntimeError(
            "huggingface_hub is required to download GGUFs. uv sync, then retry."
        ) from exc
    target = dest_dir or MODELS_DIR
    target.mkdir(parents=True, exist_ok=True)
    logger.info("Downloading {} from {}", spec.filename, spec.repo_id)
    path = hf_hub_download(
        repo_id=spec.repo_id,
        filename=spec.filename,
        local_dir=str(target),
    )
    logger.info("Saved {}", path)
    return Path(path)


def ensure_gguf(settings: LlmEndpointSettings) -> Path:
    """Download the actor GGUF when ``models/`` does not already have it."""
    spec = spec_for(settings)
    if spec is None:
        raise ValueError(
            f"No GGUF catalog entry for local actor id={settings.id!r} model={settings.model!r}"
        )
    path = gguf_path(spec)
    if path.is_file():
        return path
    model_id = (settings.id or "").strip()
    if model_id not in GGUF_SPECS:
        model_id = next(k for k, v in GGUF_SPECS.items() if v is spec)
    return download_gguf(model_id, MODELS_DIR)


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Return True when something accepts TCP on ``host:port``."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        try:
            return sock.connect_ex((host, port)) == 0
        except OSError:
            return False


def pids_listening(port: int) -> list[int]:
    """Return PIDs with a TCP LISTEN socket on ``port``."""
    if sys.platform == "win32":
        return _pids_listening_windows(port)
    return _pids_listening_linux(port)


def _pids_listening_windows(port: int) -> list[int]:
    """Parse ``netstat -ano`` LISTEN rows for ``port``."""
    proc = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        check=False,
    )
    found: list[int] = []
    for line in proc.stdout.splitlines():
        upper = line.upper()
        if "LISTEN" not in upper:
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        local = parts[1] if parts[0].upper() == "TCP" else parts[0]
        if _local_addr_port(local) != port:
            continue
        try:
            pid = int(parts[-1])
        except ValueError:
            continue
        if pid > 10:
            found.append(pid)
    return sorted(set(found))


def _pids_listening_linux(port: int) -> list[int]:
    """Discover LISTEN PIDs with ``ss`` then ``lsof``."""
    found = _pids_from_ss(port)
    if found:
        return found
    return _pids_from_lsof(port)


def _pids_from_ss(port: int) -> list[int]:
    """Parse ``ss -ltnp`` ``pid=`` fields on LISTEN rows for ``port``."""
    proc = subprocess.run(
        ["ss", "-ltnp"],
        capture_output=True,
        text=True,
        check=False,
    )
    found: list[int] = []
    for line in proc.stdout.splitlines():
        if "LISTEN" not in line.upper():
            continue
        tokens = line.split()
        if not any(
            _local_addr_port(token) == port or token.endswith(f":{port}") for token in tokens
        ):
            continue
        for marker in line.replace(")", " ").replace(",", " ").split():
            if not marker.startswith("pid="):
                continue
            try:
                pid = int(marker.split("=", 1)[1])
            except ValueError:
                continue
            if pid > 0:
                found.append(pid)
    return sorted(set(found))


def _pids_from_lsof(port: int) -> list[int]:
    """Return PIDs from ``lsof -iTCP:port -sTCP:LISTEN -t``."""
    proc = subprocess.run(
        ["lsof", "-nP", f"-iTCP:{port}", "-sTCP:LISTEN", "-t"],
        capture_output=True,
        text=True,
        check=False,
    )
    found: list[int] = []
    for line in proc.stdout.splitlines():
        try:
            pid = int(line.strip())
        except ValueError:
            continue
        if pid > 0:
            found.append(pid)
    return sorted(set(found))


def _local_addr_port(addr: str) -> int | None:
    """Parse ``127.0.0.1:8082`` or ``[::1]:8082`` into a port."""
    if addr.startswith("[") and "]:" in addr:
        try:
            return int(addr.rsplit("]:", 1)[1])
        except ValueError:
            return None
    if ":" not in addr:
        return None
    try:
        return int(addr.rsplit(":", 1)[1])
    except ValueError:
        return None


def owned_llama(port: int) -> OwnedLlama | None:
    """Return the llama-server this process started on ``port``, if any."""
    return _OWNED.get(port)


def _close_log(owned: OwnedLlama) -> None:
    """Close a retained server log handle."""
    if owned.log_file is None:
        return
    try:
        owned.log_file.close()
    except OSError:
        pass
    owned.log_file = None


def _log_tail(path: Path | None, n: int = 2000) -> str:
    """Return the last characters of a llama-server log."""
    if path is None or not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")[-n:]


def stop_owned(port: int) -> None:
    """Kill the llama-server this process started on ``port``."""
    owned = _OWNED.pop(port, None)
    if owned is None:
        return
    logger.info("Stopping owned {} PID {} on port {}", owned.alias, owned.proc.pid, port)
    kill_process_tree(owned.proc)
    _close_log(owned)
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and is_port_open(port):
        time.sleep(0.4)


def stop_port(port: int, *, stale_ok: bool = True) -> None:
    """Stop the owned child on ``port``, then any leftover listener."""
    stop_owned(port)
    if not is_port_open(port):
        return
    pids = pids_listening(port)
    if not pids:
        return
    if not stale_ok:
        raise RuntimeError(f"Port {port} still has listeners {pids} after owned stop")
    for pid in pids:
        logger.warning(
            "Stopping stale listener PID {} on port {} (not an owned llama-server)",
            pid,
            port,
        )
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/F", "/T"],
                capture_output=True,
                check=False,
            )
        else:
            subprocess.run(
                ["kill", "-TERM", str(pid)],
                capture_output=True,
                check=False,
            )
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline and is_port_open(port):
        time.sleep(0.4)


def _server_model_ids(base_url: str) -> list[str]:
    """Return ``/v1/models`` ids, or empty if the server is not ready."""
    url = base_url.rstrip("/") + "/models"
    try:
        response = httpx.get(url, timeout=3.0)
        response.raise_for_status()
        payload = response.json()
    except (httpx.HTTPError, ValueError):
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    ids: list[str] = []
    for item in data:
        if isinstance(item, dict) and item.get("id"):
            ids.append(str(item["id"]))
    return ids


def wait_ready(
    base_url: str,
    timeout_sec: float = 300.0,
    *,
    proc: subprocess.Popen[Any] | None = None,
    monotonic_fn: Callable[[], float] | None = None,
    wall_fn: Callable[[], float] | None = None,
    sleep_fn: Callable[[float], None] | None = None,
    models_fn: Callable[[str], list[str]] | None = None,
    heartbeat_sec: float = 15.0,
) -> bool:
    """Poll ``/v1/models`` until the server answers or either clock expires."""
    deadline = Deadline(timeout_sec, monotonic_fn=monotonic_fn, wall_fn=wall_fn)
    sleep = sleep_fn or time.sleep
    models = models_fn or _server_model_ids
    last_beat = deadline.mono_start
    mono = monotonic_fn or time.monotonic
    while not deadline.expired():
        if proc is not None and proc.poll() is not None:
            logger.warning(
                "llama-server exited {} before ready at {}",
                getattr(proc, "returncode", proc.poll()),
                base_url,
            )
            return False
        if models(base_url):
            return True
        now = mono()
        if heartbeat_sec > 0 and now - last_beat >= heartbeat_sec:
            logger.info(
                "Waiting for {} ({:.0f}s remaining)",
                base_url,
                deadline.remaining(),
            )
            last_beat = now
        sleep(min(2.0, max(0.1, deadline.remaining())))
    return False


def _start_llama(
    settings: LlmEndpointSettings,
    spec: GgufSpec,
    gguf: Path,
    *,
    timeout_sec: float = 300.0,
    log_dir: Path | None = None,
    options: LlamaLaunchOptions | None = None,
) -> OwnedLlama:
    """Spawn llama-server for ``spec`` on the actor's configured port."""
    exe = llama_server_exe()
    if not exe.is_file():
        raise FileNotFoundError(
            f"llama-server not found at {exe}. Set LLAMA_SERVER_EXE in .env."
        )
    opts = options or llama_launch_options()
    base = local_base_url(settings)
    port = port_from_base_url(base)
    args = [
        str(exe),
        "-m",
        str(gguf),
        "--alias",
        spec.alias,
        "--jinja",
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "-c",
        str(spec.context),
        "--parallel",
        str(opts.parallel),
        "-t",
        str(opts.threads),
        "--threads-batch",
        str(opts.threads),
    ]
    if opts.n_gpu_layers > 0:
        args.extend(["-ngl", str(opts.n_gpu_layers)])
    elif opts.n_gpu_layers == 0:
        # Explicit CPU-only; omit -ngl so older binaries still start.
        pass
    if opts.flash_attn and flash_attn_supported(exe):
        args.extend(["-fa", "on"])
    flags = 0
    if sys.platform == "win32":
        flags = int(getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x00000200)) | _CREATE_NO_WINDOW
    log_path: Path | None = None
    log_file: TextIO | None = None
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / f"{settings.path_id()}.log"
        log_file = log_path.open("w", encoding="utf-8")
    logger.info("Starting {} on port {} ({})", spec.alias, port, gguf.name)
    env = os.environ.copy()
    lib_dirs = [str(exe.resolve().parent)]
    cuda_home = os.getenv("CUDA_HOME", "").strip()
    if cuda_home:
        lib_dirs.append(str(Path(cuda_home) / "lib64"))
    previous = env.get("LD_LIBRARY_PATH", "")
    env["LD_LIBRARY_PATH"] = ":".join([*lib_dirs, previous] if previous else lib_dirs)
    stdout = log_file if log_file is not None else subprocess.DEVNULL
    proc = subprocess.Popen(
        args,
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=stdout,
        stderr=subprocess.STDOUT if log_file is not None else subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=flags,
    )
    owned = OwnedLlama(
        proc=proc,
        port=port,
        alias=spec.alias,
        exe=str(exe),
        log_path=log_path,
        log_file=log_file,
    )
    _OWNED[port] = owned
    if wait_ready(base, timeout_sec, proc=proc):
        logger.info(
            "{} ready at {} pid={} elapsed_budget={:.0f}s",
            spec.alias,
            base,
            proc.pid,
            timeout_sec,
        )
        return owned
    exit_code = proc.poll()
    tail = _log_tail(log_path)
    stop_owned(port)
    detail = tail.strip() or "no server log captured"
    raise TimeoutError(
        f"{spec.alias} did not become ready at {base} within {timeout_sec:.0f}s "
        f"(pid={proc.pid}, exit={exit_code}). {detail}"
    )


def stop_local_actors(actors: list[LlmEndpointSettings]) -> None:
    """Stop owned llama-server children, then leftover listeners on actor ports."""
    ports: set[int] = set(_OWNED)
    for settings in actors:
        if not is_local_provider(settings.provider):
            continue
        ports.add(port_from_base_url(local_base_url(settings)))
    for port in sorted(ports):
        stop_port(port)


def ensure_local_actor(
    settings: LlmEndpointSettings,
    peers: list[LlmEndpointSettings],
    *,
    timeout_sec: float = 300.0,
    log_dir: Path | None = None,
) -> OwnedLlama | None:
    """Stop other local actors, then make this one reachable if it is local."""
    if not is_local_provider(settings.provider):
        stop_local_actors(peers)
        return None
    keep_port = port_from_base_url(local_base_url(settings))
    for peer in peers:
        if not is_local_provider(peer.provider):
            continue
        peer_port = port_from_base_url(local_base_url(peer))
        if peer_port != keep_port:
            stop_port(peer_port)
    spec = spec_for(settings)
    if spec is None:
        raise ValueError(
            f"Local actor {settings.id or settings.model} is not in the GGUF catalog"
        )
    gguf = ensure_gguf(settings)
    base = local_base_url(settings)
    owned = owned_llama(keep_port)
    if owned is not None and owned.proc.poll() is None:
        ids = _server_model_ids(base)
        if spec.alias in ids or settings.model in ids:
            logger.info(
                "{} already serving on port {} pid={}",
                spec.alias,
                keep_port,
                owned.proc.pid,
            )
            return owned
        logger.info("Owned process on port {} has the wrong model {}; restarting", keep_port, ids)
        stop_owned(keep_port)
    elif is_port_open(keep_port):
        ids = _server_model_ids(base)
        if spec.alias in ids or settings.model in ids:
            logger.info("{} already serving on port {} (external listener)", spec.alias, keep_port)
            return None
        logger.info("Port {} has the wrong model {}; restarting", keep_port, ids)
        stop_port(keep_port)
    return _start_llama(
        settings,
        spec,
        gguf,
        timeout_sec=timeout_sec,
        log_dir=log_dir,
    )


def _cli(argv: list[str] | None = None) -> None:
    """Manual start/stop: ``python -m rasa_skill_eval.local_llm start lfm-1.2b``."""
    import argparse

    from rasa_skill_eval.config import load_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "stop"))
    parser.add_argument(
        "ids",
        nargs="*",
        help="Actor ids from config.yaml. Default start: lfm-1.2b lfm-2.6b",
    )
    args = parser.parse_args(argv)
    cfg = load_config()
    by_id = {a.path_id(): a for a in cfg.llm.agents}
    names = [n.strip() for n in args.ids if n.strip()]
    if args.action == "stop":
        chosen = [by_id[n] for n in names if n in by_id] if names else list(cfg.llm.agents)
        stop_local_actors(chosen)
        return
    if not names:
        names = ["lfm-1.2b", "lfm-2.6b"]
    for name in names:
        actor = by_id.get(name)
        if actor is None:
            raise SystemExit(f"{name} is not in config.yaml llm.agents")
        ensure_local_actor(
            actor,
            list(cfg.llm.agents),
            timeout_sec=cfg.eval.local_startup_timeout_sec,
        )


if __name__ == "__main__":
    _cli()
