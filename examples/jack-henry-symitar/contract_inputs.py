# SPDX-License-Identifier: MIT
"""Load privately fetched, pinned Symitar OpenAPI inputs without network access.

Vendor documents are not bundled or relicensed here. The caller supplies the
four exact downloaded byte strings. A different release needs reviewed pins.
Requires PyYAML and openapi-schema-validator (OpenAPI 3.0 semantics).
"""
from __future__ import annotations

import hashlib
from typing import Mapping

import yaml
from openapi_schema_validator import OAS30ReadValidator, OAS30WriteValidator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

SOURCE_BASE = "https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/"
PINS = {
    "accounts": "ea8fa652705d2c5531f3dcea4d18c5797797423e8a51a4a2a0403f471615228f",
    "transactions": "c1659b038b1d7bd9c89a63ad2e688a27d89cbc1d18477627d9e0105d87f10d96",
    "loans": "050962d37b56c1a35eddb7795b3fa9e4c1c6db10b01f4f5b2b46a9f4537092a5",
    "transfers": "bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95",
}
OPERATIONS = frozenset({
    "findAccountBy", "findAccountByWithBalances", "searchAccountTransactions",
    "searchLoans", "calculateLoanPayoffQuote", "postTransfer",
})


class ContractError(Exception):
    """Closed, redacted failure; never includes vendor content or YAML errors."""


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


class SymitarContract:
    """Pinned operation schemas; does not certify provider deployment semantics."""

    def __init__(self, inputs: Mapping[str, bytes]):
        self._operations = {}
        try:
            if set(inputs) != set(PINS):
                raise ContractError("missing_contract")
            for family, digest in PINS.items():
                raw = inputs[family]
                if not isinstance(raw, bytes) or len(raw) > 1_048_576:
                    raise ContractError("invalid_contract")
                if hashlib.sha256(raw).hexdigest() != digest:
                    raise ContractError("contract_drift")
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

    def response(self, operation_id: str, status: int, media: str, body: object) -> None:
        try:
            _, _, responses = self._operations[operation_id]
            content = responses.get(str(status), responses.get("default"))
            if content is None or media not in content:
                raise ContractError("invalid_response")
            content[media].validate(body)
        except Exception:
            raise ContractError("invalid_response") from None
