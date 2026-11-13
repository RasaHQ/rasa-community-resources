# SPDX-License-Identifier: MIT
"""Load privately fetched Symitar OpenAPI inputs without network access.

Vendor documents are not bundled or relicensed here. The caller supplies the
four downloaded byte strings. PINS records the exact files this example was
tested with (see VENDOR-FILES.md). Jack Henry serves each file from one URL
that always returns its newest version, so a learner may download newer bytes.
Then this module validates the example's own recorded traffic
(recorded_exchanges.py: every request it sends and every reply it reads) against
the supplied files, with the same validators it uses at runtime. If all of it is
still valid, the example runs and says so; if not, it stops and names the
operation and what the files no longer accept.
Requires PyYAML and openapi-schema-validator (OpenAPI 3.0 semantics).
"""
from __future__ import annotations

import hashlib
from typing import Mapping
from pathlib import Path

import yaml
from jsonschema.exceptions import best_match
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
# The vendor operations this example calls. What it sends and reads is recorded
# in recorded_exchanges.py.
OPERATIONS = frozenset({"findAccountBy", "findAccountByWithBalances", "searchAccountTransactions",
                        "searchLoans", "calculateLoanPayoffQuote", "postTransfer"})
_MAX_HOPS = 64


class ContractError(Exception):
    """Closed, redacted failure; never includes vendor content or YAML errors."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


class VendorChanged(ContractError):
    """The supplied vendor files no longer accept this example's recorded traffic.

    Each change names the operation and the validator's message, which may quote
    a schema value from the vendor file (for example an allowed enum value)."""

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
            # A chain of references that only point at further references, and comes
            # back to itself, has no schema at its end: refuse it by name.
            seen, target = [], value
            while isinstance(target, dict) and "$ref" in target:
                if target["$ref"] in seen or len(seen) > _MAX_HOPS:
                    raise ContractError("schema_reference_cycle: " + str(value["$ref"]))
                seen.append(target["$ref"])
                target = _pointer(document, target["$ref"])
        for child in value.values():
            _references(child, document)
    elif isinstance(value, list):
        for child in value:
            _references(child, document)


def _escape(value):
    return value.replace("~", "~0").replace("/", "~1")


class SymitarContract:
    """Pinned operation schemas; does not certify provider deployment semantics."""

    def __init__(self, inputs: Mapping[str, bytes]):
        self._operations = {}
        self.newer_files = ()  # families whose bytes differ from PINS but stay compatible
        try:
            if set(inputs) != set(PINS):
                raise ContractError("missing_contract")
            for family, digest in PINS.items():
                raw = inputs[family]
                if not isinstance(raw, bytes) or len(raw) > 1_048_576:
                    raise ContractError("invalid_contract")
                document = yaml.safe_load(raw)
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
                problems = self.exchange_problems()
                if problems:
                    raise VendorChanged(problems)
                self.newer_files = drifted
            if set(self._operations) != OPERATIONS:
                raise ContractError("missing_operation")
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_contract") from None

    def exchange_problems(self) -> list[str]:
        """Validate every recorded exchange with this contract's runtime validators.

        Returns one line per exchange the files no longer accept, naming the
        operation and the validator's message. If the validators cannot run on
        the files at all, raises ContractError("could_not_check").
        """
        from recorded_exchanges import EXCHANGES
        problems = []
        try:
            for operation, side, status, media, body in EXCHANGES:
                if operation not in self._operations:
                    if f"{operation} is no longer in the files" not in problems:
                        problems.append(f"{operation} is no longer in the files")
                    continue
                _, request, responses = self._operations[operation]
                label = f"{operation} request" if side == "request" else f"{operation} {status} response"
                if side == "request":
                    validator = request
                elif body is None:
                    if responses.get(str(status)) != {}:
                        problems.append(f"{label} is no longer declared without a body")
                    continue
                else:
                    content = responses.get(str(status), responses.get("default"))
                    if not content or media not in content:
                        problems.append(f"{label} ({media}) is no longer declared")
                        continue
                    validator = content[media]
                error = best_match(validator.iter_errors(body))
                if error is not None:
                    where = "/".join(str(part) for part in error.absolute_path) or "the whole body"
                    message = str(error.message)
                    if message.startswith(repr(error.instance)):  # don't repeat the recorded body
                        message = "the recorded value" + message[len(repr(error.instance)):]
                    message = " ".join(message.split())
                    problems.append(f"{label} is no longer valid at {where}: {message[:200]}")
        except Exception:
            raise ContractError("could_not_check") from None
        return problems

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
