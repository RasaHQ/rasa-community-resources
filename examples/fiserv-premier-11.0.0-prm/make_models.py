# SPDX-License-Identifier: MIT
"""Generate premier_demo/vendor_models/ from the pinned Fiserv archive (`make models`).

The models carry interface facts only: field names, types, required fields,
nullability, formats, limits and allowed values, for the one operation each of
the five pinned definitions serves, its request and the success reply the
client reads, and only the component schemas those reach. Every description, example, title and vendor extension is
removed before generation, so no vendor prose reaches the repository. The
archive itself stays in vendor-inputs/, which Git ignores.

Run it only with the pinned archive (premier_demo.contract.ARCHIVE_SHA256 and
the member pins); load_members() refuses anything else. `--check` regenerates
into a temporary folder and fails if the committed models differ, so a hand
edit is caught.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import yaml

from premier_demo.contract import ARCHIVE_SHA256, MEMBERS, SUCCESS, default_path, load_members

GENERATOR = "datamodel-code-generator==0.87.0"
OUTPUT = Path(__file__).resolve().parent / "premier_demo" / "vendor_models"
# Everything that is prose or metadata, not part of the interface. Removed only where it
# annotates a schema or an operation, never as a key of a name map or inside a literal value.
DROP = frozenset({"description", "example", "examples", "title", "externalDocs", "summary", "tags"})
# Maps whose keys are names (fields, media types, status codes, headers, links).
NAME_MAPS = frozenset({"properties", "patternProperties", "responses", "content", "headers", "links", "mapping",
                       "schemas"})
# Keywords whose value is a literal JSON value: kept exactly, never filtered.
LITERALS = frozenset({"enum", "default", "const"})
ARGUMENTS = (
    "--input-file-type", "openapi",
    "--openapi-scopes", "schemas", "paths",
    "--output-model-type", "pydantic_v2.BaseModel",
    "--target-python-version", "3.12",
    "--use-standard-collections",
    "--use-union-operator",
    "--use-annotated",
    "--field-constraints",
    "--use-operation-id-as-name",
    # Missing is not null: an optional field that is not nullable may be left out
    # (its default is Pydantic's MISSING sentinel), but an explicit null is refused,
    # as the schema says; only a field the schema marks nullable accepts null.
    "--strict-nullable",
    "--use-missing-sentinel",
    # Python names in snake_case, with the vendor's names kept as aliases (the wire form);
    # this also avoids clashes such as a field and a class both called BalType.
    "--snake-case-field",
    "--allow-population-by-field-name",
    # Exact models: a field the schema does not declare is not kept, so a field lost in
    # generation shows up in the round-trip test. (Not "forbid": the schema itself allows
    # extra fields, and the OpenAPI validators stay the authority on what a reply may carry.)
    "--extra-fields", "ignore",
    "--disable-timestamp",
    "--formatters", "black", "isort",
)


def _interface(node):
    """The schema without prose: names, types, required, nullable, enums and limits."""
    if isinstance(node, dict):
        kept = {}
        for key, value in node.items():
            if key in LITERALS:
                kept[key] = value
            elif key in NAME_MAPS and isinstance(value, dict):
                # Keys here are names, such as a field called "description": keep every one.
                kept[key] = {name: _interface(item) for name, item in value.items()}
            elif key not in DROP and not str(key).startswith("x-"):
                kept[key] = _interface(value)
        # OpenAPI 3.0: `nullable: true` beside an `enum` that does not list null still
        # rejects null (the example's runtime OAS30 validators agree), so it is not nullable.
        if kept.get("nullable") is True and isinstance(kept.get("enum"), list) and None not in kept["enum"]:
            del kept["nullable"]
        return kept
    if isinstance(node, list):
        return [_interface(value) for value in node]
    return node


def used_document(key: str, raw: bytes) -> dict:
    """The definition cut down to its one operation: the request and the success reply."""
    document = yaml.safe_load(raw)
    _, _, operation_id, path = MEMBERS[key]
    post = document["paths"][path]["post"]
    if post.get("operationId") != operation_id:
        raise SystemExit(f"Refusing to generate: {key} no longer serves {operation_id} at {path}.")
    status = SUCCESS[key]
    operation = {name: post[name] for name in ("operationId", "requestBody") if name in post}
    operation["responses"] = {status: post["responses"][status]}
    # Keep the source document's own version line; replace everything else.
    trimmed = {name: document[name] for name in document
               if name not in ("paths", "components", "info", "servers", "security", "tags", "externalDocs")}
    trimmed["info"] = {"title": key, "version": document["info"]["version"]}
    trimmed["paths"] = _interface({path: {"post": operation}})
    schemas = document.get("components", {}).get("schemas", {})
    trimmed["components"] = {"schemas": {name: _interface(schemas[name])
                                         for name in sorted(_reachable(trimmed["paths"], schemas))}}
    return trimmed


def _reachable(start, schemas) -> set[str]:
    """Names of the component schemas the kept operation reaches through $ref, directly or not."""
    found, pending = set(), [start]
    while pending:
        node = pending.pop()
        if isinstance(node, dict):
            reference = node.get("$ref")
            if isinstance(reference, str) and reference.startswith("#/components/schemas/"):
                name = reference.rsplit("/", 1)[1]
                if name not in found and name in schemas:
                    found.add(name)
                    pending.append(schemas[name])
            pending.extend(value for key, value in node.items() if key != "$ref")
        elif isinstance(node, list):
            pending.extend(node)
    return found


def header(key: str, raw: bytes) -> str:
    member = MEMBERS[key][0].split("/")[-1]
    return (
        "# SPDX-License-Identifier: MIT\n"
        f"# Generated by `make models` with {GENERATOR}; do not edit by hand.\n"
        f"# Source: Fiserv {member}, sha256 {hashlib.sha256(raw).hexdigest()}\n"
        f"# from BankingHub_Premier_api_specs.zip, sha256 {ARCHIVE_SHA256}\n"
        "# Interface facts only (names, types, required, nullable, limits, allowed values);\n"
        "# descriptions and examples are removed before generation.\n"
    )


def generate(target: Path) -> None:
    archive = default_path()
    if hashlib.sha256(archive.read_bytes()).hexdigest() != ARCHIVE_SHA256:
        raise SystemExit("Refusing to generate: the archive is not the pinned one (see VENDOR-FILES.md).")
    members = load_members(archive)  # also checks every member's pin
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        for key in MEMBERS:
            source = Path(folder) / f"{key}.json"
            source.write_text(json.dumps(used_document(key, members[key]), indent=1, sort_keys=True))
            output = Path(folder) / f"{key}.py"
            subprocess.run([str(Path(sys.executable).parent / "datamodel-codegen"), "--input", str(source),
                            "--output", str(output), *ARGUMENTS], check=True, capture_output=True)
            lines = output.read_text().splitlines(keepends=True)
            while lines and lines[0].startswith("#"):  # the generator's own header names a temporary file
                lines.pop(0)
            (target / f"{key}.py").write_text(header(key, members[key]) + "".join(lines))
    (target / "__init__.py").write_text(
        "# SPDX-License-Identifier: MIT\n"
        "\"\"\"Pydantic models generated from the pinned Fiserv Premier archive (make models).\"\"\"\n")


def main(argv) -> int:
    if "--check" in argv:
        with tempfile.TemporaryDirectory() as folder:
            fresh = Path(folder) / "vendor_models"
            generate(fresh)
            stale = [path.name for path in sorted(fresh.iterdir())
                     if not (OUTPUT / path.name).is_file() or (OUTPUT / path.name).read_text() != path.read_text()]
        if stale:
            print("premier_demo/vendor_models/ differs from a fresh generation: " + ", ".join(stale)
                  + ". Run make models.")
            return 1
        print("premier_demo/vendor_models/ matches the pinned archive.")
        return 0
    generate(OUTPUT)
    print("Wrote premier_demo/vendor_models/ from the pinned archive.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
