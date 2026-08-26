#!/usr/bin/env python3
"""Pre-flight diagnostics for the Poly voice insurance agent.

Checks everything needed before `make train` / `make inspect`:
  - Python version and uv availability
  - Configuration files (agent.yml, integrations.yml, ...)
  - Secrets in .env (license expiry, LLM key, Deepgram key)
  - Python dependencies
  - Agent structure (skills, tools, seed data)
  - Project validation (skills, memory, tool constraints)
  - Demo insurance seeding
  - Connectivity to OpenAI and Deepgram
  - Trained model artefacts

Usage:
    make verify
    # or directly:
    uv run python scripts/verify_setup.py
"""

from __future__ import annotations

import base64
import contextlib
import importlib.util
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
os.chdir(PROJECT_ROOT)
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dependency missing means setup is broken
    print("python-dotenv is not installed. Run: make install")
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

# ---------------------------------------------------------------------------
# Colour helpers
# ---------------------------------------------------------------------------

_TTY = sys.stdout.isatty()


def _c(code: str) -> str:
    return code if _TTY else ""


GREEN = _c("\033[92m")
YELLOW = _c("\033[93m")
RED = _c("\033[91m")
BLUE = _c("\033[94m")
MAGENTA = _c("\033[95m")
BOLD = _c("\033[1m")
DIM = _c("\033[2m")
RESET = _c("\033[0m")


def ok(msg: str) -> None:
    print(f"{GREEN}  ✓  {msg}{RESET}")


def warn(msg: str) -> None:
    print(f"{YELLOW}  ⚠  {msg}{RESET}")


def fail(msg: str) -> None:
    print(f"{RED}  ✗  {msg}{RESET}")


def hint(msg: str) -> None:
    print(f"{DIM}       → {msg}{RESET}")


def info(msg: str) -> None:
    print(f"{BLUE}  ℹ  {msg}{RESET}")


@contextlib.contextmanager
def _silenced():
    """Suppress stdout, stderr, and logging from noisy library calls."""
    logging.disable(logging.CRITICAL)
    devnull = open(os.devnull, "w")
    try:
        with contextlib.redirect_stdout(devnull), contextlib.redirect_stderr(devnull):
            yield
    finally:
        devnull.close()
        logging.disable(logging.NOTSET)


def section(title: str) -> None:
    print(f"\n{BLUE}{BOLD}{'─' * 62}{RESET}")
    print(f"{BLUE}{BOLD}  {title}{RESET}")
    print(f"{BLUE}{BOLD}{'─' * 62}{RESET}")


def mask(value: str) -> str:
    if len(value) > 12:
        return f"{value[:4]}...{value[-4:]}"
    return "***"


# ---------------------------------------------------------------------------
# Result tracking
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.errors = 0
        self.warnings = 0
        self.next_steps: list[str] = []

    def error(self, msg: str, fix: str | None = None) -> None:
        fail(msg)
        if fix:
            hint(fix)
        self.errors += 1

    def warning(self, msg: str, fix: str | None = None) -> None:
        warn(msg)
        if fix:
            hint(fix)
        self.warnings += 1


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_python(report: Report) -> None:
    section("Python environment")
    v = sys.version_info
    if v.major == 3 and 10 <= v.minor <= 13:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        report.error(
            f"Python {v.major}.{v.minor} detected — this project needs 3.10–3.13",
            "uv python pin 3.12 && make install",
        )

    if shutil.which("uv"):
        ok("uv is installed")
    else:
        report.error(
            "uv not found on PATH",
            "curl -LsSf https://astral.sh/uv/install.sh | sh",
        )


def check_config_files(report: Report) -> None:
    section("Configuration files")

    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        report.error("No .env file", "make env    (creates it from .env.example)")
    else:
        example = PROJECT_ROOT / ".env.example"
        if example.is_file() and env_path.read_text() == example.read_text():
            report.error(
                ".env is an unedited copy of .env.example",
                "Open .env and fill in your API keys",
            )
        else:
            ok(".env is present")

    # Classic CALM v1 leftovers poison Mantle projects — fail loudly if present.
    # endpoints.yml is allowed: Mantle still uses it for NLG / model_groups.
    for legacy in ("config.yml", "domain.yml", "credentials.yml"):
        if (PROJECT_ROOT / legacy).is_file():
            report.error(
                f"Legacy CALM v1 file present: {legacy}",
                "Remove it — this project uses agent.yml / integrations.yml (+ optional endpoints.yml)",
            )

    try:
        import yaml
    except ImportError:
        report.error("PyYAML not available", "make install")
        return

    for name in ("agent.yml", "integrations.yml", "memory.yml", "responses.yml", "endpoints.yml"):
        path = PROJECT_ROOT / name
        if not path.is_file():
            report.error(f"{name} is missing", "Restore it from git: git checkout -- " + name)
            continue
        try:
            yaml.safe_load(path.read_text())
            ok(f"{name}")
        except yaml.YAMLError as exc:
            first_line = str(exc).splitlines()[0]
            report.error(f"{name} is not valid YAML — {first_line}")
            continue

        if name in ("integrations.yml", "endpoints.yml"):
            dumped = path.read_text()
            if re.search(r"^\s*temperature\s*:", dumped, re.MULTILINE):
                report.error(
                    f"{name} sets temperature — GPT-5 reasoning models reject a non-default value",
                    "Remove the temperature key from the OpenAI model config",
                )
            if name == "integrations.yml" and "gpt-5.2" not in dumped:
                report.warning(
                    f"{name} does not mention gpt-5.2",
                    "Expected llm.model: gpt-5.2",
                )


def _commented_out_in_env(var: str) -> bool:
    """Return True when *var* appears only as a commented line in .env."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return False
    pattern = re.compile(rf"^\s*#\s*{re.escape(var)}\s*=", re.MULTILINE)
    return bool(pattern.search(env_path.read_text()))


def check_license(report: Report) -> None:
    """Validate the Rasa license and report days remaining."""
    value = os.getenv("RASA_LICENSE", "").strip()
    if not value:
        report.error(
            "RASA_LICENSE not set",
            "Get a free license at https://rasa.com/rasa-pro-developer-edition-license-key-request/",
        )
        return

    parts = value.split(".")
    if len(parts) != 3:
        report.error(
            "RASA_LICENSE is not a valid JWT",
            "Copy the full license string from your Rasa email, with no line breaks",
        )
        return

    try:
        payload_segment = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_segment))
    except Exception:
        report.error("RASA_LICENSE could not be decoded", "Re-copy the license string")
        return

    exp = payload.get("exp")
    if not exp:
        ok(f"Rasa license  {DIM}({mask(value)}, no expiry){RESET}")
        return

    expires = datetime.fromtimestamp(exp, tz=timezone.utc)
    days = (expires - datetime.now(tz=timezone.utc)).days
    if days < 0:
        report.error(
            f"Rasa license expired {abs(days)} day(s) ago ({expires:%Y-%m-%d})",
            "Request a new license and update RASA_LICENSE in .env",
        )
    elif days < 14:
        report.warning(
            f"Rasa license expires in {days} day(s) ({expires:%Y-%m-%d})",
            "Renew before your session to avoid a mid-demo failure",
        )
    else:
        ok(f"Rasa license valid for {days} more day(s)  {DIM}(expires {expires:%Y-%m-%d}){RESET}")


def check_api_key(report: Report, var: str, label: str, signup: str) -> bool:
    value = os.getenv(var, "").strip()
    if value and not value.lower().startswith(("your-", "sk-your", "<")):
        ok(f"{label}  {DIM}({var}={mask(value)}){RESET}")
        return True

    if _commented_out_in_env(var):
        report.error(
            f"{label} is commented out in .env",
            f"Remove the leading '#' from the {var}= line in .env",
        )
    else:
        report.error(f"{label} not set  ({var})", f"Add {var}=... to .env — get a key at {signup}")
    return False


def check_secrets(report: Report) -> None:
    section("Secrets (.env)")
    check_license(report)
    check_api_key(
        report,
        "OPENAI_API_KEY",
        "OpenAI API key       (LLM routing + conversation)",
        "https://platform.openai.com/api-keys",
    )
    check_api_key(
        report,
        "DEEPGRAM_API_KEY",
        "Deepgram API key     (speech-to-text AND text-to-speech)",
        "https://console.deepgram.com/",
    )

    unused = [var for var in ("RIME_API_KEY", "NEBIUS_API_KEY", "SPEECHMATICS_API_KEY") if os.getenv(var)]
    if unused:
        info(f"Unused by this project: {', '.join(unused)}  (harmless)")


def check_dependencies(report: Report) -> None:
    section("Python dependencies")
    for module, label in (
        ("rasa", "rasa-pro"),
        ("rasa.calm_v2", "rasa.calm_v2  (Skills engine)"),
        ("dotenv", "python-dotenv"),
        ("aiohttp", "aiohttp"),
        ("websockets", "websockets  (Deepgram streaming)"),
        ("dateutil", "python-dateutil  (incident date parsing)"),
    ):
        if importlib.util.find_spec(module) is not None:
            ok(label)
        else:
            report.error(f"{label} not importable", "make install")


def check_agent_structure(report: Report) -> None:
    section("Agent structure")

    skill_files = sorted(PROJECT_ROOT.glob("skills/*/skill.md"))
    if not skill_files:
        report.error("No skills found under skills/*/skill.md")
    else:
        missing_frontmatter = []
        for path in skill_files:
            text = path.read_text()
            if "name:" not in text or "description:" not in text:
                missing_frontmatter.append(path.parent.name)
        if missing_frontmatter:
            report.error(
                f"Skills missing name/description frontmatter: {', '.join(missing_frontmatter)}",
                "Every skill.md needs a name and a description (the description drives routing)",
            )
        else:
            names = ", ".join(p.parent.name for p in skill_files)
            ok(f"{len(skill_files)} skills  {DIM}({names}){RESET}")

    # `@tool.` is not a valid token — it is passed to the model verbatim and breaks turns.
    offenders = [
        path.parent.name
        for path in skill_files
        if "@tool." in path.read_text()
    ]
    if offenders:
        report.error(
            f"Invalid @tool. token in skill prose: {', '.join(offenders)}",
            "Reference tools in plain prose (Call get_claim_status). @ is only for @skill. / @block.",
        )
    else:
        ok("No @tool. tokens in skill prose")

    if not (PROJECT_ROOT / "skills" / "default_session_start" / "skill.md").is_file():
        report.error(
            "skills/default_session_start/skill.md is missing",
            "Session start must execute_tool load_customer_profile before utter_greet",
        )
    else:
        ok("default_session_start skill present")

    shared_tool_files = sorted(PROJECT_ROOT.glob("tools/*.py"))
    local_tool_files = sorted(PROJECT_ROOT.glob("skills/*/tools.py"))
    shared_count = 0
    local_count = 0
    zero_arg: list[str] = []

    def _count_tools(path: Path) -> int:
        return len(re.findall(r"^@tool\(", path.read_text(), re.MULTILINE))

    def _zero_arg_tools(path: Path) -> list[str]:
        """Heuristic: async def name(...) with no required params besides context."""
        text = path.read_text()
        found: list[str] = []
        for match in re.finditer(
            r"^async def (\w+)\(([^)]*)\)",
            text,
            re.MULTILINE,
        ):
            # Only count defs that follow an @tool decorator nearby
            start = match.start()
            window = text[max(0, start - 200) : start]
            if "@tool(" not in window:
                continue
            name, params = match.group(1), match.group(2)
            parts = [p.strip() for p in params.split(",") if p.strip()]
            required = []
            for part in parts:
                if "=" in part:
                    continue
                pname = part.split(":")[0].strip()
                if pname and pname != "context":
                    required.append(pname)
            if not required:
                label = path.name if path.parent.name == "tools" else f"{path.parent.name}/{path.name}"
                found.append(f"{label}:{name}")
        return found

    for path in shared_tool_files:
        if path.name.startswith("_"):
            continue
        shared_count += _count_tools(path)
        zero_arg.extend(_zero_arg_tools(path))
    for path in local_tool_files:
        local_count += _count_tools(path)
        zero_arg.extend(_zero_arg_tools(path))

    if shared_count + local_count == 0:
        report.error("No @tool functions found under tools/ or skills/*/tools.py")
    else:
        ok(
            f"Tools discovered  {DIM}({shared_count} shared in tools/, "
            f"{local_count} local in skills/*/tools.py){RESET}"
        )

    if zero_arg:
        info(
            "Zero-arg tools (do not rely on the LLM to call these for setup): "
            + ", ".join(zero_arg)
        )

    if (PROJECT_ROOT / "lib" / "database.py").is_file():
        ok("lib/database.py  (demo insurance helpers)")
    else:
        report.error("lib/database.py is missing")

    seeds = sorted(PROJECT_ROOT.glob("data/source/*.json"))
    if len(seeds) >= 3:
        ok(f"Seed data  {DIM}({len(seeds)} JSON files in data/source/){RESET}")
    else:
        report.error(
            f"Expected at least 3 seed files in data/source/, found {len(seeds)}",
            "Restore customers.json, policies.json, and claims.json",
        )

    # Flow YAMLs under data/ (except source/) are CALM v1 leftovers.
    flow_yamls = [
        p
        for p in PROJECT_ROOT.glob("data/**/*.yml")
        if "source" not in p.parts
    ]
    if flow_yamls:
        report.error(
            f"Legacy flow YAML(s) under data/: {', '.join(str(p.relative_to(PROJECT_ROOT)) for p in flow_yamls[:4])}",
            "Remove CALM v1 flow trees — seed JSON belongs in data/source/ only",
        )


def check_project_validation(report: Report) -> None:
    section("Project validation")
    try:
        from rasa.calm_v2.validation import validate_project
    except ImportError:
        report.error("Cannot import rasa.calm_v2.validation", "make install")
        return

    error: Exception | None = None
    with _silenced():
        try:
            validate_project(PROJECT_ROOT)
        except Exception as exc:
            error = exc

    if error is None:
        ok("Skills, memory, and tool constraints are valid")
        return

    problems = [line.strip() for line in str(error).splitlines() if line.strip().startswith("-")]
    report.error("Project validation failed")
    for problem in problems[:8]:
        hint(problem.lstrip("- ").strip())
    if len(problems) > 8:
        hint(f"...and {len(problems) - 8} more. Run: make validate")
    if not problems:
        hint(str(error).splitlines()[0])


def check_demo_data(report: Report) -> None:
    section("Demo insurance data")
    try:
        from lib.database import DEMO_CUSTOMER_ID, DEMO_FIRST_NAME, Database, get_customer
    except ImportError as exc:
        report.error(f"Cannot import the demo insurance DB: {exc}", "make install")
        return

    try:
        db = Database()
        customer = get_customer(db, DEMO_CUSTOMER_ID)
        if customer is None:
            report.error(
                f"Demo customer '{DEMO_CUSTOMER_ID}' not found in the seeded database",
                "make reset-db",
            )
            return

        policies = db.run_query(
            "SELECT policy_num FROM policies WHERE customer_id = ?",
            (DEMO_CUSTOMER_ID,),
            one_record=False,
        )
        claims = db.run_query(
            "SELECT claim_id FROM claims WHERE customer_id = ?",
            (DEMO_CUSTOMER_ID,),
            one_record=False,
        )
        ok(
            f"{DEMO_FIRST_NAME} ({DEMO_CUSTOMER_ID}): {len(policies or [])} policies, "
            f"{len(claims or [])} claims"
        )
        info("Run 'make show-demo-data' for the numbers to use during the demo")
    except Exception as exc:
        report.error(f"Demo insurance DB failed to seed: {exc}", "make reset-db")


def _probe(url: str, headers: dict[str, str], timeout: int = 20) -> tuple[str, int | str]:
    """Probe an endpoint for its status code only."""
    import socket
    import urllib.error
    import urllib.request

    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return "status", response.status
    except urllib.error.HTTPError as exc:
        return "status", exc.code
    except (socket.timeout, TimeoutError):
        return "timeout", timeout
    except urllib.error.URLError as exc:
        return "error", str(exc.reason)
    except Exception as exc:
        return "error", str(exc)


def _check_service(
    report: Report,
    label: str,
    url: str,
    headers: dict[str, str],
    key: str,
    key_var: str,
) -> None:
    if not key:
        report.warning(f"{label}: skipped ({key_var} not set)")
        return

    kind, detail = _probe(url, headers)
    if kind == "status" and detail == 200:
        ok(f"{label} reachable and key accepted")
    elif kind == "status" and detail in (401, 403):
        report.error(
            f"{label} rejected the key (HTTP {detail})",
            f"Check {key_var} in .env — copy it again from the provider console",
        )
    elif kind == "status":
        report.warning(f"{label} returned HTTP {detail}")
    elif kind == "timeout":
        report.warning(
            f"{label} did not respond within {detail}s",
            "Likely a slow network or a VPN/proxy. Retry, or continue if the key is known good",
        )
    else:
        report.error(f"{label} unreachable: {detail}", "Check your internet connection")


def check_connectivity(report: Report) -> None:
    section("Service connectivity")

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    _check_service(
        report,
        "OpenAI     (LLM)",
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {openai_key}"},
        openai_key,
        "OPENAI_API_KEY",
    )

    deepgram_key = os.getenv("DEEPGRAM_API_KEY", "").strip()
    _check_service(
        report,
        "Deepgram   (ASR + TTS)",
        "https://api.deepgram.com/v1/projects",
        {"Authorization": f"Token {deepgram_key}"},
        deepgram_key,
        "DEEPGRAM_API_KEY",
    )


def check_model(report: Report) -> None:
    section("Trained model")
    models_dir = PROJECT_ROOT / "models"
    models = sorted(models_dir.glob("*.tar.gz")) if models_dir.is_dir() else []
    if not models:
        report.warning("No trained model yet", "Run: make train")
        report.next_steps.append("make train")
        return

    newest = max(models, key=lambda p: p.stat().st_mtime)
    stamp = datetime.fromtimestamp(newest.stat().st_mtime)
    size_kb = newest.stat().st_size / 1024

    if size_kb < 10:
        report.warning(
            f"Model looks incomplete  {DIM}({newest.name}, only {size_kb:.0f} KB){RESET}",
            "A previous train probably failed. Run: make clean && make train",
        )
        report.next_steps.append("make clean && make train")
    else:
        ok(f"Model present  {DIM}({newest.name}, {size_kb:.0f} KB, built {stamp:%Y-%m-%d %H:%M}){RESET}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 62}{RESET}")
    print(f"{BOLD}{BLUE}  Poly — Pre-flight diagnostics{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 62}{RESET}")

    report = Report()

    check_python(report)
    check_config_files(report)
    check_secrets(report)
    check_dependencies(report)
    check_agent_structure(report)
    check_project_validation(report)
    check_demo_data(report)
    check_connectivity(report)
    check_model(report)

    print(f"\n{BOLD}{'=' * 62}{RESET}")

    if report.errors == 0 and report.warnings == 0:
        print(f"{GREEN}{BOLD}✓  All checks passed — you are ready to go.{RESET}")
        print()
        print(f"  {MAGENTA}Talk to Poly:{RESET}")
        print(f"    {GREEN}make inspect{RESET}")
    elif report.errors == 0:
        print(f"{YELLOW}{BOLD}⚠  Ready, with {report.warnings} warning(s) noted above.{RESET}")
        print()
        next_command = report.next_steps[0] if report.next_steps else "make inspect"
        print(f"  {MAGENTA}Next:{RESET}")
        print(f"    {GREEN}{next_command}{RESET}")
    else:
        print(f"{RED}{BOLD}✗  {report.errors} error(s) found — fix these first.{RESET}")
        if report.warnings:
            print(f"{YELLOW}  Also {report.warnings} warning(s) noted above.{RESET}")
        print()
        print(f"  {BLUE}Common fixes:{RESET}")
        print(f"    {GREEN}make install{RESET}          reinstall dependencies")
        print(f"    {GREEN}make env{RESET}              create .env, then fill in your keys")
        print(f"    {GREEN}make reset-db{RESET}         reseed the demo insurance DB")

    print()
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
