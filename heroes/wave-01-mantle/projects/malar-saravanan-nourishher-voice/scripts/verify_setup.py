#!/usr/bin/env python3
"""Pre-flight diagnostics for the NourishHer voice nutrition agent.

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
        "OpenAI API key       (LLM orchestrator, primary)",
        "https://platform.openai.com/api-keys",
    )
    check_api_key(
        report,
        "GROQ_API_KEY",
        "Groq API key         (LLM orchestrator, fallback only)",
        "https://console.groq.com/keys",
    )
    check_api_key(
        report,
        "GEMINI_API_KEY",
        "Gemini API key       (reference-doc embeddings)",
        "https://aistudio.google.com/apikey",
    )
    check_api_key(
        report,
        "DEEPGRAM_API_KEY",
        "Deepgram API key     (speech-to-text AND text-to-speech)",
        "https://console.deepgram.com/",
    )

    usda_key = os.getenv("USDA_FDC_API_KEY", "").strip()
    if usda_key and usda_key != "DEMO_KEY":
        ok(f"USDA FoodData Central key  {DIM}(USDA_FDC_API_KEY={mask(usda_key)}){RESET}")
    else:
        report.warning(
            "USDA_FDC_API_KEY not set — falling back to the shared DEMO_KEY",
            "Optional: get your own free key at https://fdc.nal.usda.gov/api-key-signup",
        )


def check_dependencies(report: Report) -> None:
    section("Python dependencies")
    for module, label in (
        ("rasa", "rasa-pro"),
        ("dotenv", "python-dotenv"),
        ("dateutil", "python-dateutil"),
        ("httpx", "httpx"),
    ):
        if importlib.util.find_spec(module) is not None:
            ok(label)
        else:
            report.error(f"{label} not importable", "make install")

    if importlib.util.find_spec("rasa.mantle") is not None:
        ok("rasa.mantle  (Mantle Skills engine)")
    else:
        report.error("rasa.mantle is not importable", "make install")


def check_agent_structure(report: Report) -> None:
    section("Agent structure")

    skill_files = sorted(PROJECT_ROOT.glob("skills/*/skill.md"))
    expected_skills = {
        "intro",
        "intake_profile",
        "update_profile",
        "meal_planning",
        "meal_logging",
        "meal_history",
        "coaching_checkin",
        "nutrition_qna",
        "professional_referral",
        "hypothyroidism_reminder_gate",
        "hypothyroidism_nutrition",
        "pcos_nutrition",
        "diabetes_nutrition",
        "fertility_nutrition",
        "safety_escalation",
        "goodbye",
    }
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

        found = {p.parent.name for p in skill_files}
        missing = expected_skills - found
        if missing:
            report.warning(f"Expected skills not found: {', '.join(sorted(missing))}")
        else:
            ok(f"{len(skill_files)} skills  {DIM}({', '.join(sorted(found))}){RESET}")

    tools_path = PROJECT_ROOT / "tools" / "nutrition.py"
    if not tools_path.is_file():
        report.error("tools/nutrition.py is missing")
    else:
        tool_count = len(re.findall(r"^@tool\(", tools_path.read_text(), re.MULTILINE))
        if tool_count:
            ok(f"tools/nutrition.py  {DIM}({tool_count} shared tool(s)){RESET}")
        else:
            report.error("tools/nutrition.py defines no @tool functions")

    local_tools = sorted(PROJECT_ROOT.glob("skills/*/tools.py"))
    if local_tools:
        labels = ", ".join(p.parent.name for p in local_tools)
        ok(f"{len(local_tools)} skill-local tools.py  {DIM}({labels}){RESET}")
    else:
        report.warning("No skill-local tools.py found")

    if (PROJECT_ROOT / "lib" / "usda_client.py").is_file():
        ok("lib/usda_client.py  (USDA FoodData Central client)")
    else:
        report.error("lib/usda_client.py is missing")


def check_project_validation(report: Report) -> None:
    section("Project validation")
    validate = None
    try:
        from rasa.mantle.validation import validate_project as validate
    except ImportError:
        try:
            from rasa.calm_v2.validation import validate_project as validate  # type: ignore
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


def _probe(url: str, headers: dict[str, str], timeout: int = 20) -> tuple[str, int | str]:
    # Use httpx, not urllib — some providers front their API with Cloudflare
    # bot-fingerprint detection that blocks urllib's bare TLS signature with a
    # generic 403 ("error code: 1010") even for a fully valid key. Reproduced
    # directly against Groq during this project's own setup: urllib got 403,
    # httpx (and a real LiteLLM completion call) got 200 with the same key.
    import httpx

    try:
        response = httpx.get(url, headers=headers, timeout=timeout)
        return "status", response.status_code
    except httpx.TimeoutException:
        return "timeout", timeout
    except OSError as exc:
        return "error", str(exc)
    except httpx.HTTPError as exc:
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


def _normalize_ssl_cert_file(report: Report) -> None:
    """SSL_CERT_FILE must point at a real CA bundle or httpx crashes on every probe."""
    cert = os.environ.get("SSL_CERT_FILE", "").strip()
    if not cert:
        return

    path = Path(cert)
    if not path.is_file():
        # Common on Windows: .env.example uses macOS `.venv/lib/...` (lowercase lib).
        alt = cert.replace("/lib/", "/Lib/").replace("\\lib\\", "\\Lib\\")
        if alt != cert:
            alt_path = Path(alt)
            if alt_path.is_file():
                os.environ["SSL_CERT_FILE"] = str(alt_path)
                report.warning(
                    "SSL_CERT_FILE used a macOS-style path (lib/); corrected to Lib/",
                    f"Update .env to: SSL_CERT_FILE={alt_path.as_posix()}",
                )
                ok(f"SSL_CERT_FILE corrected to {alt_path}")
                return

        report.error(
            f"SSL_CERT_FILE is set but not found: {cert}",
            "Remove SSL_CERT_FILE from .env unless you need it for SSL errors. "
            "On Windows use .venv/Lib/site-packages/certifi/cacert.pem",
        )
        return

    ok(f"SSL_CERT_FILE  {DIM}({path}){RESET}")


def check_connectivity(report: Report) -> None:
    section("Service connectivity")
    _normalize_ssl_cert_file(report)
    if report.errors:
        return

    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    _check_service(
        report,
        "OpenAI     (LLM, primary)",
        "https://api.openai.com/v1/models",
        {"Authorization": f"Bearer {openai_key}"},
        openai_key,
        "OPENAI_API_KEY",
    )

    groq_key = os.getenv("GROQ_API_KEY", "").strip()
    _check_service(
        report,
        "Groq       (LLM, fallback)",
        "https://api.groq.com/openai/v1/models",
        {"Authorization": f"Bearer {groq_key}"},
        groq_key,
        "GROQ_API_KEY",
    )

    gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
    _check_service(
        report,
        "Gemini     (rephraser + embeddings)",
        f"https://generativelanguage.googleapis.com/v1beta/models?key={gemini_key}",
        {},
        gemini_key,
        "GEMINI_API_KEY",
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

    usda_key = os.getenv("USDA_FDC_API_KEY", "").strip() or "DEMO_KEY"
    _check_service(
        report,
        "USDA FDC   (nutrient data)",
        f"https://api.nal.usda.gov/fdc/v1/foods/search?api_key={usda_key}&query=egg&pageSize=1",
        {},
        usda_key,
        "USDA_FDC_API_KEY",
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
    print(f"{BOLD}{BLUE}  NourishHer — Pre-flight diagnostics{RESET}")
    print(f"{BOLD}{BLUE}{'=' * 62}{RESET}")

    report = Report()

    check_python(report)
    check_config_files(report)
    check_secrets(report)
    check_dependencies(report)
    check_agent_structure(report)
    check_project_validation(report)
    check_connectivity(report)
    check_model(report)

    print(f"\n{BOLD}{'=' * 62}{RESET}")

    if report.errors == 0 and report.warnings == 0:
        print(f"{GREEN}{BOLD}✓  All checks passed — you are ready to go.{RESET}")
        print()
        print(f"  {MAGENTA}Talk to NourishHer:{RESET}")
        print(f"    {GREEN}make inspect{RESET}")
    elif report.errors == 0:
        print(f"{YELLOW}{BOLD}⚠  Ready, with {report.warnings} warning(s) noted above.{RESET}")
        next_command = report.next_steps[0] if report.next_steps else "make inspect"
        print(f"  {MAGENTA}Next:{RESET} {GREEN}{next_command}{RESET}")
    else:
        print(f"{RED}{BOLD}✗  {report.errors} error(s) found — fix these first.{RESET}")
        print(f"  {GREEN}make install{RESET} / {GREEN}make env{RESET}")

    print()
    sys.exit(1 if report.errors else 0)


if __name__ == "__main__":
    main()
