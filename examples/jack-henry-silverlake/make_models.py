# SPDX-License-Identifier: MIT
"""Generate silverlake_demo/vendor_models/ from the pinned Jack Henry archive (`make models`).

xsdata turns the two pinned jXchange master schemas into Python dataclasses,
one module each (inquiry.py, transaction.py). The full output is very large, so
this script keeps only the classes the client uses, by reference from the
request and response root elements of its six operations: anything reachable
through field annotations, base classes, nested classes and default values.
The pruning works on the generated code's syntax tree, keeps the kept classes
in xsdata's own order with the module imports they need, and is the same on
every run. Nothing is edited by hand.

One exception: AcctInqResponse is not kept. Its reply tree alone is about
49,000 generated lines, and the client reads two values from it. Only the loan
payment record the client reads (LnAcctInqRec / x_LnInfoRec / LnInfoRec), and
what that record reaches, is kept.

The models carry interface facts only. xsdata is run with --docstring-style
Blank, and the script refuses to write a module that contains any docstring or
any of the archive's xs:documentation text. The archive itself stays in
vendor-inputs/, which Git ignores.

Run it only with the pinned archive; anything else is refused. `--check`
regenerates into a temporary folder and returns 1 if the committed modules
differ, so a hand edit is caught.
"""
from __future__ import annotations

import ast
import hashlib
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import typing

from silverlake_demo.contract import ARCHIVE_NAME, ARCHIVE_SHA256, WSDLS, ContractError, default_path, extract

GENERATOR = "xsdata==26.10"
FORMATTER = "ruff==0.17.3"
OUTPUT = Path(__file__).resolve().parent / "silverlake_demo" / "vendor_models"
NS = "http://jackhenry.com/jxchange/TPG/2008"
LINE_LENGTH = 100
# Every generator option is written out, so a change of xsdata defaults cannot change the output.
ARGUMENTS = (
    "--output", "dataclasses",
    "--structure-style", "single-package",
    "--docstring-style", "Blank",
    "--max-line-length", str(LINE_LENGTH),
    "--no-include-header",
    "--no-relative-imports",
    "--no-compound-fields",
    "--no-wrapper-fields",
    "--no-unnest-classes",
    "--no-ignore-patterns",
    "--no-generic-collections",
    "--repr", "--eq", "--no-order", "--no-unsafe-hash", "--no-frozen", "--no-slots",
)
# module -> (master schema, request and response root elements kept with all they reach)
MODULES = {
    "inquiry": ("TPG_InquiryMaster.xsd", (
        "AcctSrch", "AcctSrchResponse", "AcctBalInq", "AcctBalInqResponse", "AcctHistSrch",
        "AcctHistSrchResponse", "AcctInq", "LnPayoffInq", "LnPayoffInqResponse")),
    "transaction": ("TPG_TransactionMaster.xsd", ("XferAdd", "XferAddResponse")),
}
# AcctInqResponse is left out; this is the only part of it that is kept (with all it reaches).
LOAN_PAYMENT = ("inquiry", "AcctInqResponse", ("LnAcctInqRec", "x_LnInfoRec", "LnInfoRec"))
EXCEPTION_LINE = ("# AcctInqResponse is not kept (its reply tree alone is about 49,000 lines); only the\n"
                  "# loan payment record LnAcctInqRec / x_LnInfoRec / LnInfoRec, and what it reaches, is.\n")
DOCUMENTATION = re.compile(rb"<(?:[\w.-]+:)?documentation\b[^>]*>(.*?)</(?:[\w.-]+:)?documentation>", re.S)


def _imported(folder: Path, name: str) -> list[str]:
    """The master schema and every archive member it imports or includes, directly or not."""
    found, pending = [], [name]
    while pending:
        member = pending.pop(0)
        if member in found:
            continue
        found.append(member)
        raw = (folder / member).read_bytes()
        for location in re.findall(rb'schemaLocation\s*=\s*"([^"]+)"', raw):
            location = location.decode("ascii")
            if "/" not in location and (folder / location).is_file():
                pending.append(location)
    return found


class _Module:
    """The generated module's top-level classes, read from its syntax tree."""

    def __init__(self, source: str):
        self.source = source
        self.tree = ast.parse(source)
        self.classes = {node.name: node for node in self.tree.body if isinstance(node, ast.ClassDef)}

    def references(self, name: str) -> set[str]:
        """Top-level classes one class names: annotations, bases, nested classes, defaults, string forward refs."""
        names = set()
        for node in ast.walk(self.classes[name]):
            if isinstance(node, ast.Name):
                names.add(node.id)
            elif isinstance(node, ast.AnnAssign):
                # A quoted forward reference; other strings (XML names in metadata) are not references.
                for item in ast.walk(node.annotation):
                    if isinstance(item, ast.Constant) and isinstance(item.value, str):
                        try:
                            expression = ast.parse(item.value, mode="eval")
                        except SyntaxError:
                            continue
                        names.update(part.id for part in ast.walk(expression) if isinstance(part, ast.Name))
        return {item for item in names if item in self.classes and item != name}

    def closure(self, roots) -> set[str]:
        kept, pending = set(), list(roots)
        while pending:
            name = pending.pop()
            if name in kept:
                continue
            if name not in self.classes:
                raise SystemExit(f"Refusing to generate: {name} is no longer in the generated module.")
            kept.add(name)
            pending.extend(self.references(name))
        return kept

    def _field_type(self, name: str, element: str) -> str:
        """The class of the field that carries `element` on class `name` (or one of its bases)."""
        node = self.classes.get(name)
        while node is not None:
            for statement in node.body:
                if not isinstance(statement, ast.AnnAssign) or not isinstance(statement.value, ast.Call):
                    continue
                metadata = next((keyword.value for keyword in statement.value.keywords
                                 if keyword.arg == "metadata"), None)
                if isinstance(metadata, ast.Dict) and any(
                        isinstance(key, ast.Constant) and key.value == "name"
                        and isinstance(value, ast.Constant) and value.value == element
                        for key, value in zip(metadata.keys, metadata.values)):
                    types = [item.id for item in ast.walk(statement.annotation)
                             if isinstance(item, ast.Name) and item.id in self.classes]
                    if len(types) == 1:
                        return types[0]
            bases = [base.id for base in node.bases if isinstance(base, ast.Name)]
            node = self.classes.get(bases[0]) if bases else None
        raise SystemExit(f"Refusing to generate: {name} no longer carries {element} as one class.")

    def path_type(self, root: str, path) -> str:
        name = root
        for element in path:
            name = self._field_type(name, element)
        return name

    def pruned(self, kept: set[str]) -> str:
        """Module-level statements (imports) and the kept classes, in their original order."""
        lines = self.source.splitlines(keepends=True)
        parts = []
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef) and node.name not in kept:
                continue
            start = min([node.lineno, *(item.lineno for item in getattr(node, "decorator_list", []))])
            parts.append("".join(lines[start - 1:node.end_lineno]).rstrip() + "\n")
        return "\n\n".join(parts)


def _tool(name: str) -> str:
    return str(Path(sys.executable).parent / name)


def _ruff(path: Path, config: Path) -> None:
    """The same lint fixes and formatting xsdata applies, run again after pruning (drops unused imports)."""
    for command in (["check", "--fix", "--unsafe-fixes", "--exit-zero", "--quiet"], ["format", "--quiet"]):
        subprocess.run([_tool("ruff"), *command, "--no-cache", "--config", str(config),
                        "--config", f"line-length={LINE_LENGTH}", str(path)], check=True, capture_output=True)


def _ruff_config() -> Path:
    import xsdata.formats.dataclass as dataclass_format
    return Path(dataclass_format.__file__).parent / "ruff.toml"


def _header(folder: Path, members: list[str], kept: int) -> str:
    sources = "".join(f"#   {member} sha256 {hashlib.sha256((folder / member).read_bytes()).hexdigest()}\n"
                      for member in members)
    return (
        "# SPDX-License-Identifier: MIT\n"
        f"# Generated by `make models` with {GENERATOR} and {FORMATTER}; do not edit by hand.\n"
        f"# Source: Jack Henry {members[0]} and the schemas it imports, from {ARCHIVE_NAME}\n"
        f"# (sha256 {ARCHIVE_SHA256}):\n"
        f"{sources}"
        "# Interface facts only (element and attribute names, types, required and optional\n"
        "# fields, allowed values); generated without docstrings, so no vendor documentation.\n"
        f"# Kept: {kept} classes reachable from the request and response elements the client uses.\n"
        f"{EXCEPTION_LINE}"
    )


def _check_no_prose(text: str, folder: Path, members: list[str]) -> None:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and ast.get_docstring(node) is not None:
            raise SystemExit("Refusing to write: the generated code contains a docstring.")
    flat = " ".join(text.split())
    for member in members:
        for match in DOCUMENTATION.finditer((folder / member).read_bytes()):
            prose = " ".join(match.group(1).decode("utf-8", "replace").split())
            if len(prose) >= 20 and prose in flat:
                raise SystemExit("Refusing to write: vendor documentation text reached the generated code.")


def _check_complete(path: Path, kept: set[str]) -> None:
    """Every kept class resolves all of its annotations inside the pruned module."""
    name = "_vendor_models_check"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)  # our own generated module
        for item in kept:
            typing.get_type_hints(getattr(module, item), vars(module))
    finally:
        del sys.modules[name]


def _generate_module(folder: Path, module: str, work: Path) -> tuple[str, int]:
    master, roots = MODULES[module]
    run = work / module
    run.mkdir()
    env = dict(os.environ, PATH=str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""))
    subprocess.run([_tool("xsdata"), "generate", str(folder / master), "--package", module, *ARGUMENTS],
                   cwd=run, env=env, check=True, capture_output=True)
    generated = _Module((run / f"{module}.py").read_text())
    roots = list(roots)
    if module == LOAN_PAYMENT[0]:
        roots.append(generated.path_type(LOAN_PAYMENT[1], LOAN_PAYMENT[2]))
    kept = generated.closure(roots)
    if LOAN_PAYMENT[1] in kept:
        raise SystemExit(f"Refusing to generate: {LOAN_PAYMENT[1]} became reachable from a kept class.")
    pruned = run / "pruned.py"
    pruned.write_text(generated.pruned(kept))
    _ruff(pruned, _ruff_config())
    _check_complete(pruned, kept)
    members = _imported(folder, master)
    text = _header(folder, members, len(kept)) + pruned.read_text()
    _check_no_prose(text, folder, members)
    return text, len(kept)


def generate(target: Path) -> dict[str, int]:
    archive = default_path()
    try:
        raw = archive.read_bytes()
    except FileNotFoundError:
        raise SystemExit(f"Refusing to generate: vendor-inputs/{ARCHIVE_NAME} is missing (make download).") from None
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise SystemExit("Refusing to generate: the archive is not the pinned one (see VENDOR-FILES.md).")
    try:
        folder = extract(archive)
    except ContractError as error:
        raise SystemExit(f"Refusing to generate: {error}") from None
    for name, digest in WSDLS.items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest:
            raise SystemExit(f"Refusing to generate: {name} is not the pinned one.")
    counts = {}
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as work:
        for module in MODULES:
            text, counts[module] = _generate_module(folder, module, Path(work))
            (target / f"{module}.py").write_text(text)
    (target / "__init__.py").write_text(
        "# SPDX-License-Identifier: MIT\n"
        "# Generated by `make models`; do not edit by hand.\n"
        "# Dataclasses generated with xsdata from the pinned Jack Henry jXchange schemas.\n")
    return counts


def main(argv) -> int:
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as folder:
            fresh = Path(folder) / "vendor_models"
            generate(fresh)
            stale = [path.name for path in sorted(fresh.iterdir())
                     if not (OUTPUT / path.name).is_file() or (OUTPUT / path.name).read_text() != path.read_text()]
        if stale:
            print("silverlake_demo/vendor_models/ differs from a fresh generation: " + ", ".join(stale)
                  + ". Run make models.")
            return 1
        print("silverlake_demo/vendor_models/ matches the pinned archive.")
        return 0
    counts = generate(OUTPUT)
    print("Wrote silverlake_demo/vendor_models/ from the pinned archive: "
          + ", ".join(f"{module}.py {count} classes" for module, count in counts.items()) + ".")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
