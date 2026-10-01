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


def _hunk_start(header: str, side: str) -> int:
    m = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header)
    return int(m.group(1) if side == "a" else m.group(2)) if m else 0


def _baseline_copy(folder: Path, diff: Path) -> Optional[Path]:
    """A temporary copy of the folder with the diff reversed (the guard-off side), or None."""
    import shutil
    import subprocess
    import tempfile

    tmp = Path(tempfile.mkdtemp(prefix="guard-off-"))
    target = tmp / folder.name
    shutil.copytree(folder, target, ignore=shutil.ignore_patterns(".venv", "models", ".rasa", "__pycache__"))
    done = subprocess.run(["patch", "-R", "-E", "-s", "-p1", "-i", str(diff)], cwd=target,
                          capture_output=True, text=True)
    return target if done.returncode == 0 else None


def count_diff(diff: Path, folder: Optional[Path] = None) -> dict:
    """Added and removed lines of a unified diff, by the same line rule as the tree count.

    Blank lines and lines that are only a comment in their file's syntax do
    not count; in Markdown, frontmatter comments count as comments only when
    they start with ``#``. Python docstrings do not count either: when the
    framework folder is given, the counter reads the shipped file for added
    lines and a copy with the diff reversed (the guard-off baseline) for
    removed lines, and skips lines inside a module, class or function
    docstring on that side. Without the folder it cannot tell a docstring from
    code, and says so (``docstrings_excluded: false``).
    """
    baseline = _baseline_copy(folder, diff) if folder is not None else None
    doc_cache: dict[tuple[str, str], set[int]] = {}

    def docstrings(side: str, rel: str) -> set[int]:
        key = (side, rel)
        if key not in doc_cache:
            root = folder if side == "b" else baseline
            path = (root / rel) if root is not None else None
            doc_cache[key] = _docstring_lines(path.read_text(encoding="utf-8")) \
                if path is not None and path.suffix == ".py" and path.is_file() else set()
        return doc_cache[key]

    added = removed = docstring_added = docstring_removed = 0
    files: dict[str, dict[str, int]] = {}
    current = None
    a_line = b_line = 0
    for line in diff.read_text(encoding="utf-8").splitlines():
        if line.startswith("+++ "):
            current = line[4:].split("\t")[0].removeprefix("b/")
            files.setdefault(current, {"added": 0, "removed": 0})
            continue
        if line.startswith("@@"):
            a_line, b_line = _hunk_start(line, "a"), _hunk_start(line, "b")
            continue
        if line.startswith(("--- ", "diff ", "# ")) or current is None:
            continue
        if not line or line[0] not in "+- ":
            continue
        kind = line[0]
        body = line[1:].strip()
        number = b_line if kind == "+" else a_line
        if kind in " -":
            a_line += 1
        if kind in " +":
            b_line += 1
        if kind == " ":
            continue
        path = Path(current)
        prefixes = _comment_prefixes(path)
        if not body or (prefixes and body.startswith(prefixes)) or (path.suffix == ".md" and body.startswith("#")):
            continue
        if (folder is not None and baseline is not None
                and number in docstrings("b" if kind == "+" else "a", current)):
            if kind == "+":
                docstring_added += 1
            else:
                docstring_removed += 1
            continue
        if kind == "+":
            added += 1
            files[current]["added"] += 1
        else:
            removed += 1
            files[current]["removed"] += 1
    return {"diff": diff.name, "added": added, "removed": removed, "changed": added + removed,
            "docstrings_excluded": baseline is not None,
            "docstring_lines_skipped": {"added": docstring_added, "removed": docstring_removed},
            "files": files}


# ----------------------------------------------------------------------------
# Shared prompt text restated in a framework's own files
# ----------------------------------------------------------------------------


def _shared_corpus() -> str:
    """The shared instruction text, normalised: every string cedar_clinic.instructions exports."""
    clinic = Path(__file__).resolve().parents[1] / "clinic"
    if str(clinic) not in sys.path:
        sys.path.insert(0, str(clinic))
    from cedar_clinic import instructions, refills

    parts = [instructions.PERSONA, *instructions.RULES, instructions.VOICE_RULES, instructions.GREETING,
             instructions.PROCEDURE, refills.confirmation_question("{selected_medication_label}"),
             refills.DECLINED_TEXT]
    return _norm(" ".join(parts))


def _norm(text: str) -> str:
    text = text.replace("@tool.", "").replace("\u2019", "'")
    return " ".join(re.sub(r"[^a-z0-9{}' ]+", " ", text.lower()).split())


_YAML_SCAFFOLD_RE = re.compile(r"^(?:-\s*)?(?:[a-z_]+:\s*)?(?:[>|]-?)?\s*[\"']?|[\"']\s*$")


def shared_text_lines(root: Path) -> dict:
    """Counted lines whose text restates the shared instruction text, by concern.

    A line counts as restated when, stripped of YAML list and key syntax and
    quotes, it is at least four words long and appears word for word in the
    text ``cedar_clinic.instructions`` exports (Mantle's ``@tool.`` prefix
    ignored). A version that imports the text has none. Reported so agent
    logic can be compared with and without instruction text.
    """
    corpus = _shared_corpus()
    out: dict[str, int] = defaultdict(int)
    files: dict[str, int] = {}
    for path in counted_files(root):
        if path.suffix not in {".md", ".yml", ".yaml", ".txt"}:
            continue
        default = file_concern(path, root)
        if default in (None, "regions"):
            default = _mapped_tag(path, root) or "untagged"
        stack: list[str] = []
        n = 0
        for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if BEGIN_RE.search(line) and line.startswith(("#", "<!--")):
                stack.append(BEGIN_RE.search(line).group(1))
                continue
            if END_RE.search(line) and line.startswith(("#", "<!--")):
                if stack:
                    stack.pop()
                continue
            if not line or line.startswith(("#", "<!--")):
                continue
            text = _norm(_YAML_SCAFFOLD_RE.sub("", line))
            if len(text.split()) >= 4 and text in corpus:
                out[stack[-1] if stack else default] += 1
                n += 1
        if n:
            files[path.relative_to(root).as_posix()] = n
    return {"by_concern": dict(out), "total": sum(out.values()), "files": files}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("folder", help="framework folder, e.g. rasa, langgraph or strands")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--diff", action="store_true", help="count the folder's guard.diff instead")
    parser.add_argument("--shared-text", action="store_true",
                        help="count lines that restate the shared instruction text, by concern")
    args = parser.parse_args()
    if args.shared_text:
        report = shared_text_lines(Path(args.folder).resolve())
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"{args.folder}: {report['total']} counted lines restate cedar_clinic.instructions "
                  f"{report['by_concern']}")
            for name, n in report["files"].items():
                print(f"  {name:<40} {n}")
        return 0
    if args.diff:
        folder = Path(args.folder).resolve()
        report = count_diff(folder / "guard.diff", folder)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            skipped = report["docstring_lines_skipped"]
            print(f"{args.folder}/guard.diff: +{report['added']} -{report['removed']} counted lines "
                  f"({report['changed']} changed) in {len(report['files'])} files; docstrings "
                  f"{'excluded' if report['docstrings_excluded'] else 'NOT excluded'} "
                  f"(+{skipped['added']} -{skipped['removed']} skipped)")
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
