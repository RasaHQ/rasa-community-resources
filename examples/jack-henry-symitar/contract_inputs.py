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
# sha256 of used_surface() for the files in PINS. Each used field is recorded by its
# whole schema (every validation keyword, refs inlined, allOf/oneOf/anyOf kept;
# only documentation keys such as description and example are left out), plus
# the paths, the required lists around sent fields and the own rules of every
# container passed on the way to a used field (e.g. additionalProperties, maxItems). Any difference stops
# start-up. It cannot see a change of meaning that keeps the shape.
USED_SURFACE_SHA256 = "7e552338bc06440c4d1a426aa695b9ba8bdcee6977cba9240e8a06a591aec89d"


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


_MAX_HOPS = 64


def _follow(node, document, stack):
    """Follow local $refs with a cycle guard; returns (schema, references followed)."""
    while isinstance(node, dict) and "$ref" in node:
        reference = node["$ref"]
        if reference in stack:
            raise ContractError("schema_reference_cycle: " + str(reference))
        if len(stack) >= _MAX_HOPS:
            raise ContractError("schema_too_deep")
        stack = stack + (reference,)
        node = _pointer(document, reference)
    return node, stack


def _resolve(node, document, stack=()):
    """A schema with $refs followed and allOf merged, to find properties and required lists."""
    node, stack = _follow(node, document, stack)
    if isinstance(node, dict) and "allOf" in node:
        merged = {key: value for key, value in node.items() if key != "allOf"}
        properties, required = dict(merged.get("properties", {})), list(merged.get("required", []))
        for part in node["allOf"]:
            part = _resolve(part, document, stack)
            properties.update(part.get("properties", {}))
            required += part.get("required", [])
            for key in ("type", "nullable", "items"):
                if key in part and key not in merged:
                    merged[key] = part[key]
        merged["properties"], merged["required"] = properties, sorted(set(required))
        node = merged
    return node if isinstance(node, dict) else {}


# Keys that only document a schema; every other key counts as validation.
_DOC_ONLY = frozenset({"description", "example", "examples", "title", "externalDocs", "deprecated", "xml"})


def _canonical(node, document, stack=()):
    """The whole schema of a used field: refs inlined, allOf/oneOf/anyOf kept, every
    validation keyword included. Any difference in it counts as a change (fail closed)."""
    if len(stack) > _MAX_HOPS:
        raise ContractError("schema_too_deep")
    if isinstance(node, dict):
        if "$ref" in node:
            target, deeper = _follow(node, document, stack)
            return _canonical(target, document, deeper)
        return {key: _canonical(value, document, stack) for key, value in sorted(node.items())
                if key not in _DOC_ONLY and not str(key).startswith("x-")}
    if isinstance(node, list):
        return [_canonical(value, document, stack) for value in node]
    return node


def _describe(schema, document):
    return _canonical(schema, document)


_COMPOSITIONS = ("allOf", "oneOf", "anyOf")


def _container(raw, document, stack=()):
    """A container passed on the way to a used field, from its unmerged schema: every
    rule except its children (properties, items, required lists) and documentation,
    including the rules inside each allOf, oneOf and anyOf part. Sibling fields the
    example does not use are left out; the container's own rules count."""
    node, stack = _follow(raw, document, stack)
    if not isinstance(node, dict):
        return node
    own = {}
    for key, value in node.items():
        if key in ("properties", "items", "required") or key in _DOC_ONLY or str(key).startswith("x-"):
            continue
        if key in _COMPOSITIONS and isinstance(value, list):
            own[key] = [_container(part, document, stack) for part in value]
        else:
            own[key] = _canonical(value, document, stack)
    return own


def _walk(schema, path, document, required_trail, containers):
    """The unresolved schema of the field at path. Records the required list of each
    object passed (for sent fields) and every container's own rules (both directions)."""
    node, raw = _resolve(schema, document), schema
    for token in [t for t in path.split(".") if t]:
        name, is_items = (token[:-2], True) if token.endswith("[]") else (token, False)
        if name:
            containers.append(_container(raw, document))
            if required_trail is not None:
                required_trail.append(sorted(node.get("required", [])))
            properties = node.get("properties", {})
            if name not in properties:
                return None
            raw = properties[name]
            node = _resolve(raw, document)
        if is_items:
            containers.append(_container(raw, document))
            if "items" not in node:
                return None
            raw = node["items"]
            node = _resolve(raw, document)
    return raw


def used_surface(documents: Mapping[str, dict]) -> dict:
    """Exactly what this example relies on, extracted from parsed vendor documents."""
    surface = {}
    for document in documents.values():
        for path, methods in document.get("paths", {}).items():
            for method, operation in methods.items():
                name = operation.get("operationId") if isinstance(operation, dict) else None
                if name not in USED:
                    continue
                entry = {"method": method, "path": path, "sends": {}, "required": [], "reads": {},
                         "containers": {}}
                request = operation.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
                for field in USED[name]["sends"]:
                    trail, containers = [], []
                    node = _walk(request, field, document, trail, containers) if request is not None else None
                    entry["sends"][field] = _describe(node, document) if node is not None else "missing"
                    entry["required"].append(trail)
                    entry["containers"]["sends " + field] = containers
                ok = operation.get("responses", {}).get("200", {})
                schema = ok.get("content", {}).get("application/json", {}).get("schema")
                entry["reads"]["200"] = "present" if schema is not None else "missing"
                for field in USED[name]["reads"]:
                    containers = []
                    node = _walk(schema, field, document, None, containers) if schema is not None else None
                    entry["reads"][field] = _describe(node, document) if node is not None else "missing"
                    entry["containers"]["reads " + field] = containers
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
        for field in sorted(set(old.get("containers", {})) | set(new.get("containers", {}))):
            if old.get("containers", {}).get(field) != new.get("containers", {}).get(field):
                side, path = field.split(" ", 1)
                changes.append(f"{name} {'request' if side == 'sends' else 'response'} structure around {path} changed")
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
