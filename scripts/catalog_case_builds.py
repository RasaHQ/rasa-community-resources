#!/usr/bin/env python3
"""Index every casebook case build: catalog/case-builds.json and CATALOG.md.

A case build is an `examples/mantle-<mode>-<case>-<model>[-local]` project with
a `case-build/` folder. Every field in the index is read from the build itself
(README, agent.yml, integrations.yml, case-build/ results and spend ledger),
from the casebook contract in tutorials/rasa-ai-team-casebook/examples/, from
the voice vendor router's vendor table, or from a recorded snapshot of the
rasa.community casebook (catalog/casebook-site.json). A field that cannot be
read is null. Nothing is estimated.

Stdlib only, no network, deterministic: the same tree always produces the
same bytes, so `make validate` can fail when the committed files are stale.

Usage:
    python3 scripts/catalog_case_builds.py            # write both files
    python3 scripts/catalog_case_builds.py --check    # exit 1 if either is stale
    python3 scripts/catalog_case_builds.py --site ../rasa-community --site-ref origin/main
        # first refresh catalog/casebook-site.json from a local site checkout
        # (industry and publication state of each casebook article), then write
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CATALOG_JSON = Path("catalog/case-builds.json")
CATALOG_MD = Path("CATALOG.md")
SITE_SNAPSHOT = Path("catalog/casebook-site.json")
CASEBOOK = Path("tutorials/rasa-ai-team-casebook")
ROUTER = Path("patterns/voice-vendor-router")
HARNESS = Path("scripts/case_builds")
FLUX_EVIDENCE = Path("examples/mantle-voice-banking-block-card-gpt/case-build/flux-short-reply")
SITE_URL = "https://rasa.community"

BUILD_RE = re.compile(r"^mantle-(text|voice)-(.+)-(gpt|gemini|claude)(-local)?$")

# LiteLLM provider prefix -> the company that serves the model.
PROVIDER_VENDORS = {"openai": "OpenAI", "anthropic": "Anthropic", "gemini": "Google"}
# Harness channel id -> the channel as run.
CHANNELS = {"rest": "web chat", "browser_audio": "browser audio"}


# --------------------------------------------------------------------------
# Small readers
# --------------------------------------------------------------------------

def _read(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def _json(path: Path):
    text = _read(path)
    if text is None:
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _scalar(raw: str):
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "'\"":
        return raw[1:-1]
    if raw in ("true", "false"):
        return raw == "true"
    if raw in ("null", "~", ""):
        return None
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    if re.fullmatch(r"-?\d+\.\d+", raw):
        return float(raw)
    return raw


def _strip_comment(line: str) -> str:
    quote = None
    for i, ch in enumerate(line):
        if quote:
            if ch == quote:
                quote = None
        elif ch in "'\"":
            quote = ch
        elif ch == "#" and (i == 0 or line[i - 1] in " \t"):
            return line[:i].rstrip()
    return line.rstrip()


def mini_yaml(text: str):
    """Parse the block-style YAML subset the case builds use.

    Mappings, lists of scalars or mappings, quoted and plain scalars, and
    `|`/`>` block scalars. No flow collections, anchors or multi-documents:
    a file that needs them is outside what this index reads, and the caller
    turns the ValueError into nulls.
    """
    lines: list[tuple[int, str]] = []
    raw_lines = text.splitlines()
    i = 0
    while i < len(raw_lines):
        raw = raw_lines[i]
        stripped = _strip_comment(raw)
        if stripped.strip():
            indent = len(stripped) - len(stripped.lstrip(" "))
            body = stripped.strip()
            if re.search(r":\s*[|>][-+]?$", body):
                # Block scalar: swallow every deeper-indented or blank line.
                block: list[str] = []
                j = i + 1
                while j < len(raw_lines):
                    nxt = raw_lines[j]
                    if nxt.strip() and len(nxt) - len(nxt.lstrip(" ")) <= indent:
                        break
                    block.append(nxt.strip())
                    j += 1
                key = body.split(":", 1)[0]
                lines.append((indent, f"{key}: {json.dumps(' '.join(b for b in block if b))}"))
                i = j
                continue
            if body.startswith(("{", "[", "&", "*", "---")):
                raise ValueError(f"unsupported YAML construct: {body[:30]!r}")
            lines.append((indent, body))
        i += 1

    def parse(pos: int, indent: int):
        if pos >= len(lines):
            return None, pos
        if lines[pos][1].startswith("- ") or lines[pos][1] == "-":
            items = []
            while pos < len(lines) and lines[pos][0] == indent and lines[pos][1].startswith("-"):
                rest = lines[pos][1][1:].strip()
                if not rest:
                    value, pos = parse(pos + 1, lines[pos + 1][0]) if pos + 1 < len(lines) else (None, pos + 1)
                    items.append(value)
                    continue
                if re.match(r"^[^'\"\s][^:]*:(\s|$)", rest):
                    # "- key: value" opens a mapping whose other keys sit at indent + 2.
                    lines[pos] = (indent + 2, rest)
                    value, pos = parse(pos, indent + 2)
                    items.append(value)
                    continue
                items.append(_scalar(rest))
                pos += 1
            return items, pos
        mapping: dict = {}
        while pos < len(lines) and lines[pos][0] == indent:
            body = lines[pos][1]
            if body.startswith("-"):
                break
            m = re.match(r"^([^:]+?):(?:\s+(.*))?$", body)
            if not m:
                raise ValueError(f"cannot parse YAML line: {body[:40]!r}")
            key, rest = m.group(1).strip().strip("'\""), m.group(2)
            if rest is not None and rest.strip():
                value = rest.strip()
                if value[0] in "{[&*":
                    raise ValueError(f"unsupported YAML value: {value[:30]!r}")
                mapping[key] = json.loads(value) if value.startswith('"') and value.endswith('"') and "\\" in value else _scalar(value)
                pos += 1
            elif pos + 1 < len(lines) and lines[pos + 1][0] > indent:
                mapping[key], pos = parse(pos + 1, lines[pos + 1][0])
            elif pos + 1 < len(lines) and lines[pos + 1][0] == indent and lines[pos + 1][1].startswith("-"):
                mapping[key], pos = parse(pos + 1, indent)
            else:
                mapping[key] = None
                pos += 1
        return mapping, pos

    if not lines:
        return {}
    value, pos = parse(0, lines[0][0])
    if pos != len(lines):
        raise ValueError("YAML indentation did not resolve")
    return value


def _yaml_file(path: Path):
    text = _read(path)
    if text is None:
        return None
    try:
        return mini_yaml(text)
    except (ValueError, IndexError):
        return None


def _get(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _plain(markdown: str) -> str:
    """Markdown inline text to plain text: links to their label, no emphasis."""
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", markdown)
    text = text.replace("**", "").replace("`", "")
    return " ".join(text.split())


# --------------------------------------------------------------------------
# README readers
# --------------------------------------------------------------------------

def readme_title(readme: str | None) -> str | None:
    if not readme:
        return None
    m = re.search(r"^# (.+)$", readme, re.M)
    return m.group(1).strip() if m else None


def readme_summary(readme: str | None) -> str | None:
    """The build's task, from 'A Rasa Mantle ... agent for one casebook case, [`x`](...): <task>.'"""
    if not readme:
        return None
    m = re.search(r"agent for one casebook case,\s*\[`[^`]+`\]\([^)]*\):\s*(.+?\.)(?=\s+[A-Z]|\s*\n\s*\n|\s*$)",
                  readme, re.S)
    if not m:
        return None
    task = _plain(m.group(1))
    return task[0].upper() + task[1:]


def main_run_dir(readme: str | None) -> str | None:
    """The results folder the README names as its main run, or None.

    Two layouts are in use: a bold lead, "**Main run** (`<dir>/`, ...)", and a
    runs table whose main row reads "| `<dir>` (main) | ...".
    """
    if not readme:
        return None
    m = re.search(r"\*\*Main run[^*]*\*\*\s*\(\s*`([^`]+?)/?`", readme)
    if m:
        return m.group(1)
    m = re.search(r"^\|\s*`([^`]+?)/?`\s*\(main\)", readme, re.M)
    return m.group(1) if m else None


def completion_run_dirs(readme: str | None) -> list[str]:
    """Results folders the README names as completion runs, in README order.

    A completion run reruns the conversations a main run lost to provider errors
    or never reached, e.g. after an API credit outage:
    "**Completion run** (`<dir>/`, ...)".
    """
    if not readme:
        return []
    return [m.group(1) for m in re.finditer(r"\*\*Completion run[^*]*\*\*\s*\(\s*`([^`]+?)/?`", readme)]


def combined_result(project: Path, runs: list[str], spec_ids: list[str] | None) -> dict | None:
    """Each conversation's latest pass or fail across the runs, in order.

    A provider error counts only when no run gave that conversation a real
    outcome; conversations no run reached are "not run".
    """
    final: dict[str, str] = {}
    for run in runs:
        results = _json(project / "case-build" / "results" / run / "results.json")
        convs = results.get("conversations") if isinstance(results, dict) else None
        if not isinstance(convs, list):
            return None
        for conv in convs:
            cid, outcome = conv.get("id"), conv.get("outcome")
            if not cid or outcome not in ("pass", "fail", "provider_error"):
                continue
            if outcome == "provider_error" and final.get(cid) in ("pass", "fail"):
                continue
            final[cid] = outcome
    counts = {o: sum(1 for v in final.values() if v == o) for o in ("pass", "fail", "provider_error")}
    not_run = len([c for c in spec_ids if c not in final]) if spec_ids else None
    return {
        "run": f"case-build/results/{runs[0]}/",
        "passed": counts["pass"],
        "total": len(final),
        "failed": counts["fail"],
        "providerErrors": counts["provider_error"],
        "notRun": not_run,
    }


def readme_findings(readme: str | None, limit: int = 3) -> list[str]:
    """The bold lead of the first `limit` items under '## What we found'."""
    if not readme:
        return []
    m = re.search(r"^## What we found\s*\n(.*?)(?=^## |\Z)", readme, re.S | re.M)
    if not m:
        return []
    findings = []
    for item in re.findall(r"^\d+\.\s+(.*?)(?=^\d+\.\s|^\S|\Z)", m.group(1), re.S | re.M):
        lead = re.match(r"\*\*(.+?)\*\*", " ".join(item.split()))
        if not lead:
            continue
        text = lead.group(1).strip().rstrip(",;:").strip()
        if text and text[-1] not in ".!?":
            text += "."
        findings.append(text)
        if len(findings) == limit:
            break
    return findings


def target_channel(readme: str | None) -> str | None:
    if not readme:
        return None
    m = re.search(r"\*\*Channel\.\*\*\s+The (?:case's |matrix )?target channel is ([A-Z][\w ]*?)\.", readme)
    return m.group(1) if m else None


def language_variant(title: str | None) -> str | None:
    """'..., in US Spanish: a voice agent ...' -> 'US Spanish'."""
    if not title:
        return None
    m = re.search(r",? in ((?:[A-Z]{2} )?[A-Z][a-z]+):", title)
    return m.group(1) if m else None


# --------------------------------------------------------------------------
# Models and speech engines
# --------------------------------------------------------------------------

def model_name(model_id: str | None) -> str | None:
    """'gpt-5.5-2026-04-23' -> 'GPT-5.5'; 'claude-sonnet-5-5' -> 'Claude Sonnet 5.5'."""
    if not model_id:
        return None
    base = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", model_id)
    if base.startswith("gpt-"):
        return "GPT-" + base[4:]
    parts = base.split("-")
    words, numbers = [], []
    for part in parts:
        if re.fullmatch(r"\d+(\.\d+)?", part):
            numbers.append(part)
        else:
            if numbers:
                words.append(".".join(numbers))
                numbers = []
            words.append(part.capitalize())
    if numbers:
        words.append(".".join(numbers))
    return " ".join(words)


def model_info(model: str | None) -> dict | None:
    if not model:
        return None
    provider, _, ident = model.partition("/")
    if not ident:
        provider, ident = None, model
    return {
        "id": ident,
        "provider": provider,
        "vendor": PROVIDER_VENDORS.get(provider or ""),
        "name": model_name(ident),
    }


def router_vendors(root: Path) -> dict[str, dict]:
    """Engine name -> vendor facts, from the router README's Vendors table."""
    text = _read(root / ROUTER / "README.md") or ""
    section = re.search(r"^## Vendors\s*\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    table: dict[str, dict] = {}
    if not section:
        return table
    for line in section.group(1).splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 5 or cells[0] in ("Vendor", "") or set(cells[0]) <= set("-: "):
            continue
        path = re.search(r"`([^`]+)`", cells[2])
        if not path:
            continue
        vendor = cells[0].replace("**", "").strip()
        entry = table.setdefault(path.group(1), {
            "vendor": vendor.split(",")[0].strip(),
            "roles": cells[1],
            "selfHosted": "local" in cells[3].lower(),
            "status": cells[4].replace("**", "").strip(),
            "row": vendor,
        })
        entry.setdefault("rows", []).append(cells[1])
    return table


def _wrapped_builtin(project: Path, engine: str) -> str | None:
    """A project-local engine class -> the Rasa built-in engine it subclasses."""
    module, _, cls = engine.rpartition(".")
    source = _read(project / (module.replace(".", "/") + ".py"))
    if not source:
        return None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    imports = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            for alias in node.names:
                imports[alias.asname or alias.name] = node.module
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in imports:
                    m = re.fullmatch(r"rasa\.core\.channels\.voice_stream\.(?:asr|tts)\.(\w+)(?:\.\w+)*",
                                     imports[base.id])
                    if m:
                        return m.group(1)
    return None


def _deepgram_family(model: str | None) -> str | None:
    if not model:
        return None
    if model.startswith("flux-general-"):
        return "Flux multi" if model.endswith("-multi") else "Flux"
    m = re.match(r"(aura-\d+)", model)
    return m.group(1).capitalize() if m else None


def speech_engine(project: Path, config, language: str | None, vendors: dict, role: str) -> dict | None:
    if not isinstance(config, dict) or not config.get("name"):
        return None
    engine = str(config["name"])
    lookup = engine
    if "." in engine and not engine.startswith("voicerouter."):
        lookup = _wrapped_builtin(project, engine) or engine
    facts = vendors.get(lookup)
    lang_map = config.get("language_map") if isinstance(config.get("language_map"), dict) else {}
    entry = lang_map.get(language) if language in lang_map else (next(iter(lang_map.values()), None) if lang_map else None)
    entry = entry if isinstance(entry, dict) else {}
    model = entry.get("model") or config.get("model_id")
    if isinstance(model, str) and "/" in model:
        model = model.rstrip("/").rsplit("/", 1)[-1]
    vendor = facts["vendor"] if facts else None
    label = vendor
    if vendor == "Deepgram" and _deepgram_family(model):
        label = f"Deepgram {_deepgram_family(model)}"
    info = {
        "engine": engine,
        "vendor": vendor,
        "model": model if isinstance(model, str) else None,
        "voice": entry.get("voice"),
        "label": label,
        "selfHosted": facts["selfHosted"] if facts else None,
    }
    if role == "asr":
        del info["voice"]
    return info


# --------------------------------------------------------------------------
# The rasa.community casebook snapshot
# --------------------------------------------------------------------------

def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---", text, re.S)
    data = {}
    if m:
        for line in m.group(1).splitlines():
            km = re.match(r"^(\w+):\s*(.*)$", line)
            if km:
                data[km.group(1)] = _scalar(km.group(2))
    return data


def _utc(value) -> datetime | None:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z", value):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def is_published(article: dict, checked_at: str) -> bool:
    """The site's rule (src/lib/casebook-publication.mjs): approved and due."""
    when, now = _utc(article.get("publishAt")), _utc(checked_at)
    return article.get("draft") is False and when is not None and now is not None and when <= now


def industry_label(name: str | None) -> str | None:
    """The site's display label (src/lib/casebook.ts, industryLabel)."""
    if not name:
        return None
    if name == "INTERNAL-facing at large organizations":
        return "Internal services"
    return re.sub(r" \(external\)$", "", name)


def read_site(site: Path, ref: str | None, as_of: str) -> dict:
    """Read every casebook article's case, industry and publication state."""
    def git(*args: str) -> str:
        return subprocess.check_output(["git", *args], cwd=site, text=True)

    folder = "src/content/casebook"
    if ref:
        names = [n for n in git("ls-tree", "--name-only", f"{ref}:{folder}").split("\n") if n.endswith(".md")]
        read = lambda name: git("show", f"{ref}:{folder}/{name}")  # noqa: E731
        revision = git("rev-parse", ref).strip()
    else:
        names = sorted(p.name for p in (site / folder).glob("*.md"))
        read = lambda name: (site / folder / name).read_text(encoding="utf-8")  # noqa: E731
        revision = git("rev-parse", "HEAD").strip()
    remote = git("remote", "get-url", "origin").strip()
    m = re.search(r"github\.com[:/](.+?)(?:\.git)?$", remote)
    cases: dict[str, dict] = {}
    for name in sorted(names):
        data = _frontmatter(read(name))
        case = data.get("case")
        if not case:
            continue
        entry = cases.setdefault(case, {"industry": data.get("industry"), "articles": []})
        entry["articles"].append({
            "id": name[:-3],
            "draft": data.get("draft"),
            "publishAt": data.get("publishAt"),
        })
    return {
        "schema": 1,
        "source": {
            "repository": m.group(1) if m else remote,
            "ref": ref or "working tree",
            "revision": revision,
            "checkedAt": as_of,
        },
        "cases": {k: cases[k] for k in sorted(cases)},
    }


def casebook_url(slug: str, site: dict | None) -> str | None:
    """The published article for this case, preferring the one named after it."""
    if not site:
        return None
    case = site.get("cases", {}).get(slug)
    if not case:
        return None
    checked = site.get("source", {}).get("checkedAt", "")
    due = sorted((a for a in case["articles"] if is_published(a, checked)),
                 key=lambda a: (a["id"] != slug, a["id"]))
    return f"{SITE_URL}/library/casebook/{due[0]['id']}/" if due else None


# --------------------------------------------------------------------------
# One build
# --------------------------------------------------------------------------

def discover_builds(root: Path) -> list[Path]:
    examples = root / "examples"
    return sorted(p for p in examples.iterdir()
                  if p.is_dir() and BUILD_RE.match(p.name) and (p / "case-build").is_dir())


def build_entry(root: Path, project: Path, site: dict | None, vendors: dict) -> dict:
    rel = project.relative_to(root).as_posix()
    mode = BUILD_RE.match(project.name).group(1)
    readme = _read(project / "README.md")
    spec = _json(project / "case-build" / "conversations.json") or {}
    slug = spec.get("case")
    contract = _json(root / CASEBOOK / "examples" / f"{slug}.json") if slug else None
    contract = contract or {}
    agent = _yaml_file(project / "agent.yml")
    integrations = _yaml_file(project / "integrations.yml")
    title = readme_title(readme)

    run = main_run_dir(readme)
    results = _json(project / "case-build" / "results" / run / "results.json") if run else None
    summary = results.get("summary") if isinstance(results, dict) else None
    result = None
    completions = completion_run_dirs(readme)
    if run and completions:
        spec_ids = [c.get("id") for c in spec.get("conversations") or [] if isinstance(c, dict)]
        result = combined_result(project, [run, *completions], spec_ids or None)
    elif isinstance(summary, dict) and isinstance(summary.get("passed"), int):
        result = {
            "run": f"case-build/results/{run}/",
            "passed": summary.get("passed"),
            "total": summary.get("conversations_run"),
            "failed": summary.get("failed"),
            "providerErrors": summary.get("provider_errors"),
            "notRun": len(summary["skipped"]) if isinstance(summary.get("skipped"), list) else None,
        }

    language = _get(agent, "agent", "language")
    asr = tts = None
    stack = "cloud"
    if mode == "voice":
        voice = _get(integrations, "channels", "browser_audio")
        asr = speech_engine(project, _get(voice, "asr"), language, vendors, "asr")
        tts = speech_engine(project, _get(voice, "tts"), language, vendors, "tts")
        local = [e.get("selfHosted") if e else None for e in (asr, tts)]
        if None in local:
            stack = None
        elif all(local):
            stack = "self-hosted speech"
        elif any(local):
            stack = "mixed"

    ledger = _json(project / "case-build" / "results" / "spend-ledger.json")
    channel_id = results.get("channel") if isinstance(results, dict) else spec.get("driver")
    case_site = (site or {}).get("cases", {}).get(slug) if slug else None
    return {
        "slug": slug,
        "path": rel,
        "title": title,
        "caseTitle": contract.get("title"),
        "organisation": contract.get("organisation") or spec.get("organisation"),
        "industry": industry_label(case_site.get("industry")) if case_site else None,
        "summary": readme_summary(readme),
        "model": model_info((results or {}).get("model") or spec.get("model")),
        "mode": mode,
        "channel": CHANNELS.get(channel_id or ""),
        "targetChannel": target_channel(readme),
        "stack": stack,
        "asr": asr,
        "tts": tts,
        "language": {"code": language, "variant": language_variant(title)} if language else None,
        "result": result,
        "spendUsd": ledger.get("total_cost_usd") if isinstance(ledger, dict) else None,
        "recordedAt": (results or {}).get("finished_at"),
        "findings": readme_findings(readme),
        "casebookUrl": casebook_url(slug, site) if slug else None,
    }


def build_catalog(root: Path = REPO_ROOT) -> dict:
    site = _json(root / SITE_SNAPSHOT)
    vendors = router_vendors(root)
    builds = [build_entry(root, p, site, vendors) for p in discover_builds(root)]
    return {
        "schema": 1,
        "generatedBy": "scripts/catalog_case_builds.py",
        "casebookSnapshot": (site or {}).get("source"),
        "count": len(builds),
        "builds": builds,
    }


def render_json(catalog: dict) -> str:
    return json.dumps(catalog, indent=2, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------
# CATALOG.md
# --------------------------------------------------------------------------

def _result_text(result: dict | None) -> str:
    if not result or result.get("total") is None:
        return "not recorded"
    text = f"{result['passed']}/{result['total']}"
    extra = []
    if result.get("providerErrors"):
        n = result["providerErrors"]
        extra.append(f"{n} provider error{'s' if n != 1 else ''}")
    if result.get("notRun"):
        extra.append(f"{result['notRun']} not run")
    return text + (f" ({', '.join(extra)})" if extra else "")


def _voice_stack(build: dict) -> str:
    if build["mode"] != "voice":
        return "—"
    parts = [(e or {}).get("label") or "unknown" for e in (build["asr"], build["tts"])]
    text = " + ".join(parts)
    return text + (" (self-hosted)" if build["stack"] == "self-hosted speech" else "")


def stack_heading(build: dict) -> str:
    name = (build["model"] or {}).get("name") or "Unknown model"
    variant = (build["language"] or {}).get("variant")
    tail = build["mode"] + (f", {variant}" if variant else "")
    if build["mode"] == "voice":
        return f"{name} + {_voice_stack(build).replace(' (self-hosted)', '')} ({tail})"
    return f"{name} ({tail})"


def _link(build: dict, prefix: str = "") -> str:
    return f"[`{build['path'].split('/', 1)[1]}`]({prefix}{build['path']}/)"


def _h1(path: Path) -> str | None:
    return readme_title(_read(path / "README.md"))


def _patterns(root: Path) -> list[tuple[str, str]]:
    """(directory, problem) from the patterns README catalog table."""
    text = _read(root / "patterns" / "README.md") or ""
    section = re.search(r"^## Catalog\s*\n(.*?)(?=^## |^---|\Z)", text, re.S | re.M)
    rows = []
    for line in (section.group(1) if section else "").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3:
            path = re.search(r"\(([^)]+)\)", cells[2])
            if path and (root / "patterns" / path.group(1)).is_dir():
                rows.append((path.group(1).rstrip("/"), cells[1]))
    return rows


def render_markdown(catalog: dict, root: Path = REPO_ROOT) -> str:
    builds = catalog["builds"]
    text_n = sum(1 for b in builds if b["mode"] == "text")
    voice_n = len(builds) - text_n
    snapshot = catalog.get("casebookSnapshot") or {}
    out: list[str] = []
    w = out.append

    w("# Catalog")
    w("")
    w("<!-- Generated by scripts/catalog_case_builds.py from catalog/case-builds.json. Do not edit by hand; run `make catalog`. -->")
    w("")
    w(f"This page indexes the {len(builds)} casebook case builds in [`examples/`](examples/) "
      f"({text_n} text, {voice_n} voice), the patterns they reuse, and the rest of the repository. "
      "Each case build is one live Rasa Mantle agent for one scenario from the "
      "[AI team casebook](tutorials/rasa-ai-team-casebook/), run through scripted conversations "
      "whose outcomes are read from the tracker. The same data is in "
      "[`catalog/case-builds.json`](catalog/case-builds.json).")
    w("")
    w("- **Result** is the build's main run as its README names it, plus any completion runs it "
      "names for conversations the main run lost or never reached: conversations passed over "
      "conversations run, each counted once at its latest outcome, from those runs' `results.json`.")
    w("- **Article** links the build's case on rasa.community once that article is published"
      + (f" (publication state read from `{snapshot.get('repository')}` at "
         f"`{(snapshot.get('revision') or '')[:7]}`, {str(snapshot.get('checkedAt', ''))[:10]})."
         if snapshot else "."))
    w("")
    w("Jump to: [by industry](#by-industry) · [by vendor stack](#by-vendor-stack) · "
      "[patterns and reusable parts](#patterns-and-reusable-parts) · "
      "[tutorials and other examples](#tutorials-and-other-examples)")
    w("")

    w("## By industry")
    w("")
    w("Industries follow the rasa.community casebook.")
    w("")
    by_industry: dict[str, list[dict]] = {}
    for b in builds:
        by_industry.setdefault(b["industry"] or "Unclassified", []).append(b)
    for industry in sorted(by_industry):
        w(f"### {industry}")
        w("")
        w("| Case | Organisation | Model | Mode | Voice stack | Result | Build | Article |")
        w("|---|---|---|---|---|---|---|---|")
        for b in sorted(by_industry[industry], key=lambda b: (b["slug"] or "", b["path"])):
            article = f"[read]({b['casebookUrl']})" if b["casebookUrl"] else "not published yet"
            mode = b["mode"] + (f" ({b['targetChannel']} target)" if b["targetChannel"] else "")
            w(f"| {b['caseTitle'] or b['slug']} | {b['organisation'] or '?'} | "
              f"{(b['model'] or {}).get('name') or '?'} | {mode} | {_voice_stack(b)} | "
              f"{_result_text(b['result'])} | {_link(b)} | {article} |")
        w("")

    w("## By vendor stack")
    w("")
    by_stack: dict[str, list[dict]] = {}
    for b in builds:
        by_stack.setdefault(stack_heading(b), []).append(b)
    for heading in sorted(by_stack, key=lambda h: (by_stack[h][0]["mode"] == "voice", h)):
        w(f"### {heading}")
        w("")
        for b in sorted(by_stack[heading], key=lambda b: b["path"]):
            recorded = f", recorded {b['recordedAt'][:10]}" if b["recordedAt"] else ""
            w(f"- {_link(b)}: {b['caseTitle'] or b['slug']}, {b['organisation'] or '?'}. "
              f"Main run {_result_text(b['result'])}{recorded}.")
        w("")

    w("## Patterns and reusable parts")
    w("")
    vendors = router_vendors(root)
    live = []
    for facts in vendors.values():
        if "live-verified" in facts["status"] and facts["vendor"] not in live:
            live.append(facts["vendor"])
    users = [b for b in builds
             if any((e or {}).get("engine", "").startswith("voicerouter.") for e in (b["asr"], b["tts"]))]
    for directory, problem in _patterns(root):
        line = f"- [`patterns/{directory}`](patterns/{directory}/): {problem.rstrip('.')}."
        if directory == ROUTER.name:
            line = (f"- [`patterns/{directory}`](patterns/{directory}/): **the voice vendor router.** "
                    f"{problem.rstrip('.')}. Its README lists {len(vendors)} ASR and TTS engines; "
                    f"live-verified: {', '.join(live)}.")
            if users:
                line += " Case builds that load its adapters directly: " + ", ".join(
                    _link(b) for b in users) + "."
        w(line)
    w(f"- [`{HARNESS.as_posix()}/`]({HARNESS.as_posix()}/): the shared case-build harness. "
      "`run_build.py` trains and starts a build, drives its scripted conversations over REST "
      "or through `voice_driver.py` (browser audio), reads each outcome from the tracker, and "
      "records results and spend. Also `render_caller_audio.py`, `call_monitor.py` and "
      "`tts_intelligibility.py`.")
    w(f"- [`{FLUX_EVIDENCE.as_posix()}/`]({FLUX_EVIDENCE.as_posix()}/): Deepgram Flux short-reply "
      "evidence. Saved Flux frames, their replay through Rasa's handler, and a patched replay: why a "
      "bare \"Yes.\" can produce no user turn.")
    contracts = len(list((root / CASEBOOK / "examples").glob("*.json")))
    w(f"- [`{CASEBOOK.as_posix()}/`]({CASEBOOK.as_posix()}/): the AI team casebook, "
      f"{contracts} case contracts (`examples/<case>.json`) that the case builds implement.")
    w("")

    w("## Tutorials and other examples")
    w("")
    w("Tutorials ([catalog](tutorials/README.md)):")
    w("")
    for path in sorted(p for p in (root / "tutorials").iterdir() if (p / "README.md").is_file()):
        w(f"- [`tutorials/{path.name}`](tutorials/{path.name}/): {_h1(path)}")
    w("")
    w("Finished example agents that are not case builds ([catalog](examples/README.md)):")
    w("")
    case_paths = {b["path"] for b in builds}
    for path in sorted(p for p in (root / "examples").iterdir()
                       if (p / "README.md").is_file() and f"examples/{p.name}" not in case_paths):
        w(f"- [`examples/{path.name}`](examples/{path.name}/): {_h1(path)}")
    w("")
    return "\n".join(out)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def outputs(root: Path = REPO_ROOT) -> dict[Path, str]:
    catalog = build_catalog(root)
    return {CATALOG_JSON: render_json(catalog), CATALOG_MD: render_markdown(catalog, root)}


def stale(root: Path = REPO_ROOT) -> list[str]:
    problems = []
    for rel, text in outputs(root).items():
        current = _read(root / rel)
        if current is None:
            problems.append(f"{rel} is missing")
        elif current != text:
            problems.append(f"{rel} is stale")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="Exit 1 if an output is missing or stale; write nothing")
    parser.add_argument("--site", type=Path, help="Local rasa.community checkout to refresh the casebook snapshot from")
    parser.add_argument("--site-ref", help="Read the site at this git ref (e.g. origin/main) instead of its working tree")
    parser.add_argument("--as-of", help="Publication cut-off, UTC ISO time ending in Z (default: now)")
    args = parser.parse_args()

    if args.check:
        problems = stale()
        for problem in problems:
            print(f"✗ {problem}; run: python3 scripts/catalog_case_builds.py", file=sys.stderr)
        return 1 if problems else 0

    if args.site:
        as_of = args.as_of or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        snapshot = read_site(args.site.resolve(), args.site_ref, as_of)
        (REPO_ROOT / SITE_SNAPSHOT).parent.mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / SITE_SNAPSHOT).write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"wrote {SITE_SNAPSHOT} ({len(snapshot['cases'])} cases, {snapshot['source']['ref']})")

    for rel, text in outputs().items():
        (REPO_ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (REPO_ROOT / rel).write_text(text, encoding="utf-8")
        print(f"wrote {rel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
