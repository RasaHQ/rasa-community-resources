#!/usr/bin/env python3
"""Count each framework's own lines per concern, the same way for all three.

    python3 shared/spec/count_concerns.py rasa            # table
    python3 shared/spec/count_concerns.py rasa --json     # per file and per concern

Stdlib only. The rules, which COMPARISON-PLAN.md states for every version:

Which files count. Every file under the framework folder except tests
(``tests/``, ``test_*.py``), documentation (``README.md``, ``AGENTS.md``,
``CLAUDE.md``, anything under ``docs/``), lockfiles (``*.lock``), secrets
templates (``.env*``), ``.gitignore``, the guard diff (``guard.diff``),
recorded results and generated folders (``.venv``, ``models``, ``.rasa``,
``__pycache__``, ``node_modules``, ``results``). Instruction files the agent
reads at runtime (a skill's ``skill.md``, a ``prompts/*.md``) do count.

What a line is. A non-blank line that is not only a comment. Python
docstrings do not count. Comment syntax: ``#`` for Python, YAML, TOML and
Makefiles; ``//`` and ``/* */`` for JavaScript and TypeScript; ``<!-- -->``
for Markdown and HTML. In Markdown, YAML frontmatter comments are comments
too. Lines are reported by kind: ``code`` (.py .js .ts .mjs, Makefile),
``config`` (.yml .yaml .toml .json .ini .cfg) and ``prose`` (.md .txt), so a
prompt written as prose and a guard written as code are not added up blindly.

Which concern a line belongs to. A comment ``concern: <tag>`` in the first 15
lines sets the file's concern. ``concern-begin: <tag>`` and ``concern-end``
comments mark a region inside a file with a different concern (the marker
lines themselves do not count). A file that cannot hold a comment (JSON) is
tagged in ``concerns.txt`` at the framework root, one ``<glob> <tag>`` per
line. Anything left over is ``untagged``. Tags used by the comparison:
``agent-logic``, ``refill-guard``, ``voice-adapter`` (the speech vendor client), ``voice-loop`` (everything else that moves audio or manages the call), ``ops``.
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Optional

SKIP_DIRS = {".venv", "venv", "models", ".rasa", "__pycache__", "node_modules", "results", "tests", "docs",
             ".whisper", ".pytest_cache", "build", "dist"}
SKIP_NAMES = {"README.md", "AGENTS.md", "CLAUDE.md", ".gitignore", "guard.diff", "concerns.txt"}
SKIP_SUFFIXES = (".lock", ".wav", ".png", ".jpg", ".pyc")
CODE = {".py", ".js", ".ts", ".mjs", ".cjs"}
CONFIG = {".yml", ".yaml", ".toml", ".json", ".ini", ".cfg"}
PROSE = {".md", ".txt"}

FILE_TAG_RE = re.compile(r"\bconcern:\s*([a-z][a-z0-9-]*)")
BEGIN_RE = re.compile(r"\bconcern-begin:\s*([a-z][a-z0-9-]*)")
END_RE = re.compile(r"\bconcern-end\b")


def kind_of(path: Path) -> Optional[str]:
    if path.name == "Makefile" or path.suffix in CODE:
        return "code"
    if path.suffix in CONFIG:
        return "config"
    if path.suffix in PROSE:
        return "prose"
    return None


def counted_files(root: Path) -> list[Path]:
    out = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if SKIP_DIRS & set(rel.parts[:-1]):
            continue
        if path.name in SKIP_NAMES or path.name.startswith(".env") or path.name.endswith(SKIP_SUFFIXES):
            continue
        if path.name.startswith("test_") or path.name.endswith("_test.py"):
            continue
        if kind_of(path) is None:
            continue
        out.append(path)
    return out


def _comment_prefixes(path: Path) -> tuple[str, ...]:
    if path.suffix in {".js", ".ts", ".mjs", ".cjs"}:
        return ("//", "/*", "*", "*/")
    if path.suffix in {".md", ".html"}:
        return ("<!--",)
    if path.suffix == ".json":
        return ()
    return ("#",)


def _docstring_lines(text: str) -> set[int]:
    """1-based line numbers covered by module, class and function docstrings."""
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return set()
    lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                lines.update(range(body[0].lineno, (body[0].end_lineno or body[0].lineno) + 1))
    return lines


def _mapped_tag(path: Path, root: Path) -> Optional[str]:
    mapping = root / "concerns.txt"
    if not mapping.is_file():
        return None
    rel = path.relative_to(root).as_posix()
    for line in mapping.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        pattern, _, tag = line.rpartition(" ")
        if pattern and fnmatch.fnmatch(rel, pattern.strip()):
            return tag.strip()
    return None


def file_concern(path: Path, root: Optional[Path] = None) -> Optional[str]:
    """The file-level tag, or 'regions' when only regions are marked, or None."""
    head = path.read_text(encoding="utf-8", errors="replace").splitlines()[:15]
    for line in head:
        if BEGIN_RE.search(line):
            continue
        m = FILE_TAG_RE.search(line)
        if m:
            return m.group(1)
    text = path.read_text(encoding="utf-8", errors="replace")
    if BEGIN_RE.search(text):
        return "regions"
    if root is not None:
        return _mapped_tag(path, root)
    return None


def count_file(path: Path, root: Path) -> dict[str, dict[str, int]]:
    """Counted lines of one file, by concern and kind.

    In Markdown, frontmatter and ``:::`` blocks are ``config`` and the rest
    is ``prose``; any other file has one kind.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    default = file_concern(path, root)
    if default == "regions" or default is None:
        default = _mapped_tag(path, root) or "untagged"
    prefixes = _comment_prefixes(path)
    docstrings = _docstring_lines(text) if path.suffix == ".py" else set()
    in_frontmatter = False
    in_fence_block = False
    in_block_comment = False
    stack: list[str] = []
    file_kind = kind_of(path) or "other"
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        begin, end = BEGIN_RE.search(line), END_RE.search(line)
        if begin and _is_comment(line, prefixes, path, in_frontmatter):
            stack.append(begin.group(1))
            continue
        if end and _is_comment(line, prefixes, path, in_frontmatter):
            if stack:
                stack.pop()
            continue
        if path.suffix == ".md" and line == "---" and (number == 1 or in_frontmatter):
            in_frontmatter = not in_frontmatter
            continue
        if not line or number in docstrings:
            continue
        if path.suffix in {".md", ".html"}:
            if in_block_comment:
                in_block_comment = "-->" not in line
                continue
            if line.startswith("<!--"):
                in_block_comment = "-->" not in line
                continue
        if path.suffix in {".js", ".ts", ".mjs", ".cjs"}:
            if in_block_comment:
                in_block_comment = "*/" not in line
                continue
            if line.startswith("/*"):
                in_block_comment = "*/" not in line
                continue
        if _is_comment(line, prefixes, path, in_frontmatter):
            continue
        kind = file_kind
        if path.suffix == ".md":
            if line.startswith(":::"):
                in_fence_block = not in_fence_block if line == ":::" or not in_fence_block else in_fence_block
                kind = "config"
            elif in_frontmatter or in_fence_block:
                kind = "config"
        counts[stack[-1] if stack else default][kind] += 1
    return {c: dict(k) for c, k in counts.items()}


def _is_comment(line: str, prefixes: tuple[str, ...], path: Path, in_frontmatter: bool) -> bool:
    if path.suffix == ".md" and in_frontmatter:
        return line.startswith("#")
    return bool(prefixes) and line.startswith(prefixes)


def count_tree(root: Path) -> dict:
    per_file = {}
    totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for path in counted_files(root):
        counts = count_file(path, root)
        per_file[path.relative_to(root).as_posix()] = counts
        for concern, kinds in counts.items():
            for kind, n in kinds.items():
                totals[concern][kind] += n
    summary = {c: {**dict(k), "total": sum(k.values())} for c, k in sorted(totals.items())}
    return {"root": root.name, "files": per_file, "concerns": summary,
            "total": sum(v["total"] for v in summary.values())}


def count_diff(diff: Path) -> dict:
    """Added and removed lines of a unified diff, by the same line rule.

    Blank lines and lines that are only a comment in their file's syntax do
    not count; in Markdown, frontmatter comments count as comments only when
    they start with ``#`` (the diff cannot tell frontmatter from body, so a
    Markdown heading would be skipped too; skill bodies here have none).
    """
    added = removed = 0
    files: dict[str, dict[str, int]] = {}
    current = None
    for line in diff.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0].removeprefix("b/")
            files.setdefault(current, {"added": 0, "removed": 0})
            continue
        if line.startswith(("--- ", "diff ", "@@", "# ")) or current is None:
            continue
        if not line or line[0] not in "+-":
            continue
        body = line[1:].strip()
        path = Path(current)
        prefixes = _comment_prefixes(path)
        if not body or (prefixes and body.startswith(prefixes)) or (path.suffix == ".md" and body.startswith("#")):
            continue
        if line[0] == "+":
            added += 1
            files[current]["added"] += 1
        else:
            removed += 1
            files[current]["removed"] += 1
    return {"diff": diff.name, "added": added, "removed": removed, "changed": added + removed, "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="framework folder, e.g. rasa, langgraph or strands")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--diff", action="store_true", help="count the folder's guard.diff instead")
    args = parser.parse_args()
    if args.diff:
        report = count_diff(Path(args.folder).resolve() / "guard.diff")
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{args.folder}/guard.diff: +{report['added']} -{report['removed']} counted lines "
                  f"({report['changed']} changed) in {len(report['files'])} files")
            for name, n in report["files"].items():
                print(f"  {name:<40} +{n['added']} -{n['removed']}")
        return 0
    root = Path(args.folder).resolve()
    if not root.is_dir():
        print(f"no such folder: {root}", file=sys.stderr)
        return 2
    report = count_tree(root)
    if args.json:
        print(json.dumps(report, indent=2))
        return 0
    print(f"{root.name}: counted lines per concern (code / config / prose)")
    for concern, kinds in report["concerns"].items():
        print(f"  {concern:<14} {kinds.get('code', 0):>5} {kinds.get('config', 0):>6} {kinds.get('prose', 0):>6}"
              f"   total {kinds['total']}")
    print(f"  {'all':<14} {'':>5} {'':>6} {'':>6}   total {report['total']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
