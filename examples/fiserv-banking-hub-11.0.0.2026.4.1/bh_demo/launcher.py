# SPDX-License-Identifier: MIT
"""One-command teaching host. No secret is printed or written to configuration."""
import argparse
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.parse import urlencode

from .client import BankingHubClient  # noqa: F401  (imported to fail early if broken)
from .contract import ContractError, MissingContractInput, BankingHubContract
from .demo_data import choose_seed, seed_line

EXPECTED_RASA = "3.21.0.dev5"
SECRETS = ("RASA_LICENSE", "OPENAI_API_KEY", "DEEPGRAM_API_KEY")


def inspector_address(port):
    name = os.environ.get("CODESPACE_NAME")
    if name:
        domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "app.github.dev")
        origin = f"https://{name}-{port}.{domain}"
    else:
        origin = f"http://localhost:{port}"
    return origin, origin + "/webhooks/inspector/inspect.html?" + urlencode(
        {"projectUrl": origin, "channel": "inspector"})


def _listener():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(128)
    return sock


def main(project):
    parser = argparse.ArgumentParser(description="Start the fictional Banking Hub release example.")
    parser.add_argument("--port", type=int, default=5005)
    parser.add_argument("--fault", choices=["none", "transfer-response-lost"], default="none",
                        help="Fictional failure scenario for the transfer, never a vendor fault.")
    parser.add_argument("--text-api", action="store_true",
                        help="Developer check: serve the REST text channel (rasa run) instead of the Inspector.")
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error("choose an unprivileged Inspector port")
    project = Path(project).resolve()
    # Each start draws new fictional amounts unless DEMO_SEED pins them; the seed is the first line.
    try:
        seed = choose_seed(os.environ)
    except ValueError as bad:
        print("Not ready. " + str(bad) + " Use DEMO_SEED=0 for the README's checked sequence.")
        return 2
    print(seed_line(seed), flush=True)
    # Step 1: the learner-supplied vendor definitions. Stop with a plain message.
    try:
        BankingHubContract.from_path()
    except MissingContractInput as missing:
        print("Not ready. " + str(missing))
        return 2
    except ContractError:
        print("Not ready. The file in vendor-inputs/ is not the expected Fiserv download. "
              "Delete it and download it again from the official page.")
        return 2
    from dotenv import load_dotenv
    load_dotenv(project / ".env", override=False)
    missing = [key for key in SECRETS if not os.environ.get(key, "").strip()]
    if missing:
        print("Not ready. Add these Codespaces secrets, then rebuild: " + ", ".join(missing)
              + ". The Fiserv mock needs no Fiserv secrets.")
        return 2
    from importlib.metadata import version
    if version("rasa-pro") != EXPECTED_RASA:
        print("Not ready. Rebuild the locked project environment; the runtime pin differs.")
        return 2
    from rasa.mantle.model_archive.snapshot import package_model_archive
    from rasa.shared.utils.yaml import read_yaml_file, write_yaml
    from .hostclient import HostClient
    origin, inspector_url = inspector_address(args.port)
    server = inspector = None
    # A plain terminate (closing the terminal, a kill) must also stop the owned services.
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        with _listener() as mock_socket, _listener() as mcp_socket:
            capability = secrets.token_urlsafe(32)
            backend_port = mcp_socket.getsockname()[1]
            environment = dict(os.environ)
            environment["BANKINGHUB_HOST_URL"] = f"http://127.0.0.1:{backend_port}"
            environment["BANKINGHUB_HOST_CAPABILITY"] = capability
            # The tool bindings import bh_demo from this folder, and the
            # Inspector runs from a temporary directory: make the import work.
            environment["PYTHONPATH"] = os.pathsep.join(
                [str(project)] + ([environment["PYTHONPATH"]] if environment.get("PYTHONPATH") else []))
            backend_environment = {key: value for key, value in os.environ.items()
                                   if key in {"PATH", "HOME", "LANG", "LC_ALL", "TMPDIR", "PYTHONPATH",
                                              "SYSTEMROOT", "BANKINGHUB_JOURNAL"}}
            backend_environment["BANKINGHUB_HOST_CAPABILITY"] = capability
            backend_environment["DEMO_SEED"] = str(seed)  # the backend builds the mock from this seed
            server = subprocess.Popen(
                [sys.executable, "-m", "bh_demo.server", str(mock_socket.fileno()),
                 str(mcp_socket.fileno()), args.fault], env=backend_environment, cwd=project,
                pass_fds=(mock_socket.fileno(), mcp_socket.fileno()))
        host = HostClient(environment["BANKINGHUB_HOST_URL"], capability)
        deadline = time.monotonic() + 20
        while True:
            if server.poll() is not None:
                if server.returncode == 4:
                    print("Not ready. Another copy of this example is still running. "
                          "Press Ctrl+C in its terminal, or close that terminal, then try again.")
                    return 1
                raise RuntimeError("backend_exited")
            try:
                session = host.open_session()
                host.reset(session)
                break
            except ValueError:
                if time.monotonic() >= deadline:
                    raise RuntimeError("backend_not_ready") from None
                time.sleep(.1)
        with tempfile.TemporaryDirectory(prefix="bankinghub-run-") as directory:
            run = Path(directory)
            result = package_model_archive(str(project / "agent.yml"), str(run / "models"),
                                           fixed_model_name="bankinghub", validate=True)
            if result.code:
                raise RuntimeError("agent_validation_failed")
            integrations = read_yaml_file(project / "integrations.yml", expand_env_vars=False)
            integrations["channels"]["inspector"]["server_url"] = origin
            write_yaml(integrations, run / "integrations.yml")
            (run / "agent.yml").write_bytes((project / "agent.yml").read_bytes())
            print("Vendor definitions: found and hash-verified. Mode: local mock built from them.")
            print("This mock uses fictional data only. It proves the conversation, not Fiserv compatibility.")
            print("Transaction history and payoff are unavailable on purpose: this release cannot supply them.")
            print("Identity: one private teaching host, a fixed simulated caller; not real bank sign-in.")
            print("Use only fictional speech. The speech provider receives audio; opt-out is not zero retention.")
            print("Open the Inspector: " + inspector_url, flush=True)
            print("To stop, press Ctrl+C in this terminal.", flush=True)
            inspector = subprocess.Popen([sys.executable, "-m", "rasa", "run" if args.text_api else "inspect", "--port", str(args.port),
                                          "--model", str(result.model)], cwd=run, env=environment)
            while inspector.poll() is None:
                if server.poll() is not None:
                    raise RuntimeError("backend_exited")
                time.sleep(.2)
            return inspector.returncode
    except KeyboardInterrupt:
        return 0
    except Exception:
        print("Not ready. An owned service failed; no secret or raw service error is shown.")
        return 1
    finally:
        for child in (inspector, server):
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
