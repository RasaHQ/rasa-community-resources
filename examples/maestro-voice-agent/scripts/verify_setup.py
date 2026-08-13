#!/usr/bin/env python3
"""Pre-flight diagnostics for the Atlas voice travel agent.

Usage:
    make verify
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
except ImportError:  # pragma: no cover
    print("python-dotenv is not installed. Run: make install")
    sys.exit(1)

load_dotenv(PROJECT_ROOT / ".env")

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


def check_python(report: Report) -> None:
    section("Python environment")
    v = sys.version_info
    if v.major == 3 and 11 <= v.minor <= 13:
        ok(f"Python {v.major}.{v.minor}.{v.micro}")
    else:
        report.error(
            f"Python {v.major}.{v.minor} detected — this project needs 3.11–3.13",
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

    for legacy in ("config.yml", "domain.yml", "credentials.yml"):
        if (PROJECT_ROOT / legacy).is_file():
            report.error(
                f"Legacy CALM v1 file present: {legacy}",
                "Remove it — this project uses agent.yml / integrations.yml only",
            )

    try:
        import yaml
    except ImportError:
        report.error("PyYAML not available", "make install")
        return

    for name in ("agent.yml", "integrations.yml", "memory.yml", "responses.yml"):
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


def _commented_out_in_env(var: str) -> bool:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return False
    pattern = re.compile(rf"^\s*#\s*{re.escape(var)}\s*=", re.MULTILINE)
    return bool(pattern.search(env_path.read_text()))


def check_license(report: Report) -> None:
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


def check_dependencies(report: Report) -> None:
    section("Python dependencies")
    for module, label in (
        ("rasa", "rasa-pro"),
        ("dotenv", "python-dotenv"),
        ("dateutil", "python-dateutil"),
    ):
        if importlib.util.find_spec(module) is not None:
            ok(label)
        else:
            report.error(f"{label} not importable", "make install")

    if importlib.util.find_spec("rasa.calm_v2") is not None:
        ok("rasa.calm_v2  (Maestro Skills engine)")
    else:
        report.error("rasa.calm_v2 is not importable", "make install")


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
                f"Skills missing name/description frontmatter: {', '.join(missing_frontmatter)}"
            )
        else:
            names = ", ".join(p.parent.name for p in skill_files)
            ok(f"{len(skill_files)} skills  {DIM}({names}){RESET}")

    tools_path = PROJECT_ROOT / "tools" / "travel.py"
    if not tools_path.is_file():
        report.error("tools/travel.py is missing")
    else:
        tool_count = len(re.findall(r"^@tool\(", tools_path.read_text(), re.MULTILINE))
        if tool_count == 2:
            ok(
                f"tools/travel.py  {DIM}"
                f"({tool_count} shared: load_customer_profile, list_bookings){RESET}"
            )
        elif tool_count:
            report.warning(
                f"tools/travel.py has {tool_count} shared tools "
                "(expected 2: load_customer_profile, list_bookings)"
            )
        else:
            report.error("tools/travel.py defines no @tool functions")

    local_tools = sorted(PROJECT_ROOT.glob("skills/*/tools.py"))
    if local_tools:
        labels = ", ".join(p.parent.name for p in local_tools)
        ok(f"{len(local_tools)} skill-local tools.py  {DIM}({labels}){RESET}")
    else:
        report.error("Expected skill-local tools.py under skills/*/tools.py")

    if (PROJECT_ROOT / "lib" / "database.py").is_file():
        ok("lib/database.py  (demo travel helpers)")
    else:
        report.error("lib/database.py is missing")

    seeds = sorted(PROJECT_ROOT.glob("data/source/*.json"))
    if len(seeds) >= 3:
        ok(f"Seed data  {DIM}({len(seeds)} JSON files in data/source/){RESET}")
    else:
        report.error(
            f"Expected at least 3 seed files in data/source/, found {len(seeds)}",
            "Restore customers.json, bookings.json, and flights.json",
        )


def check_project_validation(report: Report) -> None:
    section("Project validation")
    validate = None
    try:
        from rasa.calm_v2.validation import validate_project as validate
    except ImportError:
        try:
            from rasa.skills.validation import validate_project as validate  # type: ignore
        except ImportError:
            report.warning(
                "No project validator available in this Rasa build",
                "Structure checks above still apply — continue with make train",
            )
            return

    error: Exception | None = None
    with _silenced():
        try:
            validate(PROJECT_ROOT)
        except Exception as exc:
            error = exc

    if error is None:
        ok("Skills, memory, and tool constraints are valid")
        return

    # New Skills frontmatter may warn on older validators — keep as warning.
    report.warning(f"Validator reported issues: {str(error).splitlines()[0]}")
    hint("If train still works, you can continue. Otherwise compare skill.md to the tutorial.")


def check_demo_data(report: Report) -> None:
    section("Demo travel data")
    try:
        from lib.database import DEMO_CUSTOMER_ID, DEMO_FIRST_NAME, Database, get_customer
    except ImportError as exc:
        report.error(f"Cannot import the demo travel DB: {exc}", "make install")
        return

    try:
        db = Database()
        customer = get_customer(db, DEMO_CUSTOMER_ID)
        if customer is None:
            report.error(
                f"Demo traveler '{DEMO_CUSTOMER_ID}' not found",
                "make reset-db",
            )
            return

        bookings = db.run_query(
            "SELECT booking_ref FROM bookings WHERE customer_id = ?",
            (DEMO_CUSTOMER_ID,),
            one_record=False,
        )
        flights = db.run_query(
            "SELECT flight_number FROM flights",
            one_record=False,
        )
        ok(
            f"{DEMO_FIRST_NAME} ({DEMO_CUSTOMER_ID}): {len(bookings or [])} bookings, "
            f"{len(flights or [])} flights"
        )
        info("Run 'make show-demo-data' for the numbers to use during the demo")
    except Exception as exc:
        report.error(f"Demo travel DB failed to seed: {exc}", "make reset-db")


def _probe(url: str, headers: dict[str, str], timeout: int = 20) -> tuple[str, int | str]:
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
            f"Check {key_var} in .env",
        )
    elif kind == "status":
        report.warning(f"{label} returned HTTP {detail}")
    elif kind == "timeout":
        report.warning(f"{label} did not respond within {detail}s")
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
    ok(f"Model present  {DIM}({newest.name}, {size_kb:.0f} KB, built {stamp:%Y-%m-%d %H:%M}){RESET}")


def main() -> None:
    print(f"\n{BOLD}{BLUE}{'=' * 62}{RESET}")
    print(f"{BOLD}{BLUE}  Atlas — Pre-flight diagnostics{RESET}")
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
        print(f"  {MAGENTA}Talk to Atlas:{RESET}")
        print(f"    {GREEN}make inspect{RESET}")
    elif report.errors == 0:
        print(f"{YELLOW}{BOLD}⚠  Ready, with {report.warnings} warning(s) noted above.{RESET}")
        next_command = report.next_steps[0] if report.next_steps else "make inspect"
        print(f"  {MAGENTA}Next:{RESET} {GREEN}{next_command}{RESET}")
    else:
        print(f"{RED}{BOLD}✗  {report.errors} error(s) found — fix these first.{RESET}")
        print(f"  {GREEN}make install{RESET} / {GREEN}make env{RESET} / {GREEN}make reset-db{RESET}")

    print()
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
