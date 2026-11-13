# SPDX-License-Identifier: MIT
"""Load privately fetched Symitar OpenAPI inputs without network access.

Vendor documents are not bundled or relicensed here. The caller supplies the
four downloaded byte strings. PINS records the exact files this example was
tested with (see VENDOR-FILES.md). Jack Henry serves each file from one URL
that always returns its newest version, so a learner may download newer bytes.
Then this module checks exactly what the example uses (USED): the operations,
the request fields it sends with their types and the required fields around
them, and the success-response fields it reads. If none of that changed, the
example runs and says so; if any of it changed, it stops and names it.
Requires PyYAML and openapi-schema-validator (OpenAPI 3.0 semantics).
"""
from __future__ import annotations

import hashlib
import json
from typing import Mapping
from pathlib import Path

import yaml
from openapi_schema_validator import OAS30ReadValidator, OAS30WriteValidator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

SOURCE_BASE = "https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/"
PINS = {
    "accounts": "d6370f663f53973dfc52d931333bdc350dc39f6c2680998a9054030668b4820f",
    "transactions": "9662089e4943dea29e8d109419388bb971301890f0ca07a4a2eff55cee19fe8d",
    "loans": "2631ee0b97790009624ca3f9c8d233855d0ecf06556a8f0134770a831801c914",
    "transfers": "bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95",
}
TESTED_WITH = "Jack Henry Symitar files as published 12 Nov 2026, 22:38 UTC"  # see VENDOR-FILES.md
# Everything this example sends to or reads from each vendor operation. A path
# segment "x[]" is the items of array x; "[]" is the items of a top-level array.
USED = {
    "findAccountBy": {"sends": ("accountNumber",), "reads": ()},
    "findAccountByWithBalances": {"sends": ("accountNumber",),
                                  "reads": ("shares[].shareId", "shares[].availableBalance")},
    "searchAccountTransactions": {"sends": ("accountNumber", "shareId", "startDate", "endDate", "count", "offset"),
                                  "reads": ("transactions[].postDate", "transactions[].description",
                                            "transactions[].amount", "paging.nextOffset")},
    "searchLoans": {"sends": ("accountNumber", "loanId"), "reads": ("[].loanId", "[].paymentDue", "[].dueDate")},
    "calculateLoanPayoffQuote": {"sends": ("accountNumber", "loanId", "payoffDate"),
                                 "reads": ("totalPayoffAmount", "payoffDate")},
    "postTransfer": {"sends": ("donor.accountNumber", "donor.shareId", "recipient.accountNumber",
                               "recipient.shareId", "amount"), "reads": ("status",)},
}
OPERATIONS = frozenset(USED)
# sha256 of used_surface() for the files in PINS. It changes only when something
# in USED changes: a path, a sent or read field, its type, format, enum or
# pattern, or a newly required request field.
USED_SURFACE_SHA256 = "bc038e258b235f8c8ddf0f3eb89617c38542b567aa7f0e495420115319ca30d8"


class ContractError(Exception):
    """Closed, redacted failure; never includes vendor content or YAML errors."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


class VendorChanged(ContractError):
    """Something this example uses changed in the supplied vendor files."""

    def __init__(self, changes):
        self.changes = tuple(changes)
        super().__init__("vendor_changed: " + "; ".join(self.changes))


def load_inputs(directory: Path | None = None) -> dict[str, bytes]:
    """Read only manual vendor-inputs/<family>/<family>.yaml; never download.

    Check every present file before reporting absence, so an invalid supplied
    input cannot be hidden by a different missing file.
    """
    root = directory if directory is not None else Path(__file__).parent / "vendor-inputs"
    inputs = {}
    missing = []
    for family, digest in PINS.items():
        relative = Path(family) / (family + ".yaml")
        try:
            with (root / relative).open("rb") as source:
                raw = source.read(1_048_577)
        except FileNotFoundError:
            missing.append(relative.as_posix())
            continue
        except OSError:
            raise ContractError("vendor_input_unreadable") from None
        if len(raw) > 1_048_576:
            raise ContractError("vendor_input_invalid: " + relative.as_posix())
        if hashlib.sha256(raw).hexdigest() != digest:
            # A newer file is checked in full later; one that is not even an OpenAPI
            # document is reported now, so a missing file elsewhere cannot hide it.
            try:
                document = yaml.safe_load(raw)
            except Exception:
                document = None
            if not isinstance(document, dict) or "openapi" not in document or "paths" not in document:
                raise ContractError("vendor_input_invalid: " + relative.as_posix())
        inputs[family] = raw
    if missing:
        raise MissingContractInput(
            "Vendor definitions not supplied: manually download the pinned Symitar v1 files "
            "from " + SOURCE_BASE + " and place them in vendor-inputs/: " + ", ".join(missing)
        )
    return inputs


def _pointer(document, reference):
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise ContractError("nonlocal_reference")
    value = document
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _references(value, document):
    if isinstance(value, dict):
        if "$ref" in value:
            _pointer(document, value["$ref"])
        for child in value.values():
            _references(child, document)
    elif isinstance(value, list):
        for child in value:
            _references(child, document)


def _escape(value):
    return value.replace("~", "~0").replace("/", "~1")


def _resolve(node, document, depth=0):
    """Follow local $ref and merge allOf, enough to compare the fields used."""
    if depth > 40:
        raise ContractError("invalid_contract")
    while isinstance(node, dict) and "$ref" in node:
        node = _pointer(document, node["$ref"])
    if isinstance(node, dict) and "allOf" in node:
        merged = {key: value for key, value in node.items() if key != "allOf"}
        properties, required = dict(merged.get("properties", {})), list(merged.get("required", []))
        for part in node["allOf"]:
            part = _resolve(part, document, depth + 1)
            properties.update(part.get("properties", {}))
            required += part.get("required", [])
            for key in ("type", "nullable", "items"):
                if key in part and key not in merged:
                    merged[key] = part[key]
        merged["properties"], merged["required"] = properties, sorted(set(required))
        node = merged
    return node if isinstance(node, dict) else {}


def _describe(schema, document):
    schema = _resolve(schema, document)
    return {key: schema[key] for key in ("type", "format", "enum", "pattern", "nullable") if key in schema}


def _walk(schema, path, document, required_trail):
    """The resolved schema at path, recording the required list of each object passed."""
    node = _resolve(schema, document)
    for token in [t for t in path.split(".") if t]:
        name, is_items = (token[:-2], True) if token.endswith("[]") else (token, False)
        if name:
            if required_trail is not None:
                required_trail.append(sorted(node.get("required", [])))
            properties = node.get("properties", {})
            if name not in properties:
                return None
            node = _resolve(properties[name], document)
        if is_items:
            if "items" not in node:
                return None
            node = _resolve(node["items"], document)
    return node


def used_surface(documents: Mapping[str, dict]) -> dict:
    """Exactly what this example relies on, extracted from parsed vendor documents."""
    surface = {}
    for document in documents.values():
        for path, methods in document.get("paths", {}).items():
            for method, operation in methods.items():
                name = operation.get("operationId") if isinstance(operation, dict) else None
                if name not in USED:
                    continue
                entry = {"method": method, "path": path, "sends": {}, "required": [], "reads": {}}
                request = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
                for field in USED[name]["sends"]:
                    trail = []
                    node = _walk(request, field, document, trail) if request is not None else None
                    entry["sends"][field] = _describe(node, document) if node is not None else "missing"
                    entry["required"].append(trail)
                ok = operation.get("responses", {}).get("200", {})
                schema = ok.get("content", {}).get("application/json", {}).get("schema")
                entry["reads"]["200"] = "present" if schema is not None else "missing"
                for field in USED[name]["reads"]:
                    node = _walk(schema, field, document, None) if schema is not None else None
                    entry["reads"][field] = _describe(node, document) if node is not None else "missing"
                surface[name] = entry
    for name in USED:
        surface.setdefault(name, "missing")
    return surface


def surface_digest(surface: dict) -> str:
    return hashlib.sha256(json.dumps(surface, sort_keys=True).encode()).hexdigest()


def _changes(expected: dict, actual: dict) -> list[str]:
    changes = []
    for name in sorted(USED):
        old, new = expected.get(name), actual.get(name)
        if old == new:
            continue
        if not isinstance(new, dict):
            changes.append(name + " is no longer in the files")
            continue
        for part in ("method", "path"):
            if old.get(part) != new.get(part):
                changes.append(f"{name} {part} changed")
        for side in ("sends", "reads"):
            for field in sorted(set(old.get(side, {})) | set(new.get(side, {}))):
                if old.get(side, {}).get(field) != new.get(side, {}).get(field):
                    changes.append(f"{name} {'request' if side == 'sends' else 'response'} field {field} changed")
        if old.get("required") != new.get("required"):
            changes.append(f"{name} now requires different request fields")
    return changes or ["the operations this example uses changed"]


class SymitarContract:
    """Pinned operation schemas; does not certify provider deployment semantics."""

    def __init__(self, inputs: Mapping[str, bytes]):
        self._operations = {}
        self.newer_files = ()  # families whose bytes differ from PINS but stay compatible
        documents = {}
        try:
            if set(inputs) != set(PINS):
                raise ContractError("missing_contract")
            for family, digest in PINS.items():
                raw = inputs[family]
                if not isinstance(raw, bytes) or len(raw) > 1_048_576:
                    raise ContractError("invalid_contract")
                document = yaml.safe_load(raw)
                documents[family] = document
                if document.get("openapi") != "3.0.1" or document["info"]["version"] != "v1":
                    raise ContractError("unsupported_contract")
                _references(document, document)
                uri = "urn:symitar:" + family
                registry = Registry().with_resource(
                    uri, Resource.from_contents(document, default_specification=DRAFT4)
                )  # Default registry has no network retriever.
                for path, methods in document["paths"].items():
                    for method, operation in methods.items():
                        if not isinstance(operation, dict):
                            continue
                        name = operation.get("operationId")
                        if name not in OPERATIONS:
                            continue
                        if method != "post" or name in self._operations:
                            raise ContractError("unsupported_operation")
                        root = uri + "#/paths/" + _escape(path) + "/post"
                        request = OAS30WriteValidator(
                            {"$ref": root + "/requestBody/content/application~1json/schema"},
                            registry=registry, format_checker=OAS30WriteValidator.FORMAT_CHECKER,
                        )
                        responses = {}
                        for status, response in operation["responses"].items():
                            responses[str(status)] = {
                                media: OAS30ReadValidator(
                                    {"$ref": root + "/responses/" + _escape(str(status))
                                     + "/content/" + _escape(media) + "/schema"},
                                    registry=registry, format_checker=OAS30ReadValidator.FORMAT_CHECKER,
                                ) for media in response.get("content", {})
                            }
                        self._operations[name] = (path, request, responses)
            drifted = tuple(family for family, digest in PINS.items()
                            if hashlib.sha256(inputs[family]).hexdigest() != digest)
            if drifted:
                surface = used_surface(documents)
                if surface_digest(surface) != USED_SURFACE_SHA256:
                    from used_surface_expected import EXPECTED
                    raise VendorChanged(_changes(EXPECTED, surface))
                self.newer_files = drifted
            if set(self._operations) != OPERATIONS:
                raise ContractError("missing_operation")
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_contract") from None

    def request(self, operation_id: str, body: object) -> str:
        """Validate vendor JSON and return only its pinned path template."""
        try:
            path, validator, _ = self._operations[operation_id]
            validator.validate(body)
            return path
        except Exception:
            raise ContractError("invalid_request") from None

    def allows_empty_response(self, operation_id: str, status: int) -> bool:
        """Only an explicitly declared status without content permits no body."""
        try:
            _, _, responses = self._operations[operation_id]
            return str(status) in responses and responses[str(status)] == {}
        except Exception:
            raise ContractError("invalid_response") from None

    def response(self, operation_id: str, status: int, media: str, body: object) -> None:
        try:
            _, _, responses = self._operations[operation_id]
            if self.allows_empty_response(operation_id, status) and body is None:
                return
            content = responses.get(str(status), responses.get("default"))
            if content is None or media not in content:
                raise ContractError("invalid_response")
            content[media].validate(body)
        except Exception:
            raise ContractError("invalid_response") from None
