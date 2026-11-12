# SPDX-License-Identifier: MIT
"""Load the learner-supplied Fiserv Banking Hub release definitions.

The release ZIP is never bundled, fetched or relicensed here. The learner
downloads it by hand from Fiserv's public Resources page; this module checks the
whole archive hash, then reads only four pinned members, with hard size limits,
and builds request and response validators from those exact bytes. A changed
upstream file needs reviewed new pins, never silent acceptance.

These are Fiserv's generic Banking Hub definitions (release 11.0.0.2026.4.1).
They describe the wire shape; they do not say which values a particular core
system uses, and this example claims nothing about any specific core.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import yaml
from openapi_schema_validator import OAS30ReadValidator, OAS30WriteValidator
from referencing import Registry, Resource
from referencing.jsonschema import DRAFT4

ARCHIVE_NAME = "esf-service-swagger-release-11.0.0.2026.4.1.zip"
DOWNLOAD_PAGE = "https://developer.fiserv.com/product/BankingHub/docs/resources/resources.md?branch=main"
ARCHIVE_SHA256 = "844bb52475f442da9b96a093c3443c4d9b6a47e7c9834c509f0cf92a117f2fd3"
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_ENTRIES = 256
MAX_MEMBER = 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024
OPENAPI_VERSION = "3.0.0"

_PREFIX = "esf-service-swagger-release-11.0.0.2026.4.1/src/swagger/"
# document key -> (exact member name, member SHA256, operationId, path)
MEMBERS = {
    "party": (_PREFIX + "Bank_Sol_Org-PartyAcctRelService-11.0.0-resolved.yaml",
              "75abe3ac04300b85e176e48acaccf6597380dfab22cda4c6d4005a318cacb8c2",
              "PartyAcctRelInqBySecured", "/partyacctrel/secured"),
    "acct": (_PREFIX + "Bank_Sol_Org-AcctService-11.0.0-resolved.yaml",
             "3bcc50c8bb22e633c7cec484cd2d4216a677bbcb8d0759740d92fdce31b5e365",
             "getAccountsSecured", "/accounts/secured"),
    "trn": (_PREFIX + "Bank_Sol_Org-AcctTrnService-11.0.0-resolved.yaml",
            "1eb4d5a8a98a2be84d47356716055cf3d0e49a376e4f78056aa5e9830366267f",
            "getAcctTrnSecured", "/acctTrn/secured"),
    # Add Transfer. Its declared success is HTTP 201, not the reads' 200.
    "xfer": (_PREFIX + "Bank_Sol_Org-XferService-11.0.0-resolved.yaml",
             "ff1a683ae0bbc4ff755a9c9bc1896198a2695a6483c4552e805642c19085f0da",
             "XferAddOper", "/transfers"),
}
SUCCESS = {"party": 200, "acct": 200, "trn": 200, "xfer": 201}


class ContractError(Exception):
    """Closed, redacted failure; never carries vendor content or parser text."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


def default_path() -> Path:
    return Path(__file__).resolve().parents[1] / "vendor-inputs" / ARCHIVE_NAME


def load_members(path: Path | None = None) -> dict[str, bytes]:
    """Check the whole archive, then read only the four pinned members."""
    path = path or default_path()
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise MissingContractInput(
            "Vendor definitions not supplied. Download " + ARCHIVE_NAME + " from " + DOWNLOAD_PAGE
            + " (Download API Specifications) and save it as vendor-inputs/" + ARCHIVE_NAME
            + " inside the fiserv-banking-hub-11.0.0.2026.4.1 folder."
        ) from None
    except OSError:
        raise ContractError("vendor_input_unreadable") from None
    if size > MAX_ARCHIVE:
        raise ContractError("vendor_input_invalid")
    try:
        raw = path.read_bytes()
    except OSError:
        raise ContractError("vendor_input_unreadable") from None
    if hashlib.sha256(raw).hexdigest() != ARCHIVE_SHA256:
        raise ContractError("vendor_input_invalid")
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ENTRIES:
                raise ContractError("vendor_input_invalid")
            seen = set()
            for info in infos:
                name = info.filename
                parts = PurePosixPath(name).parts
                mode = (info.external_attr >> 16) & 0o170000
                if (name.startswith("/") or "\\" in name or ".." in parts or mode == 0o120000):
                    raise ContractError("vendor_input_invalid")
                key = re.sub(r"/+", "/", name).casefold()
                if key in seen:
                    raise ContractError("vendor_input_invalid")
                seen.add(key)
            by_name = {info.filename: info for info in infos}
            members, total = {}, 0
            for key, (name, digest, _, _) in MEMBERS.items():
                info = by_name.get(name)
                if info is None or info.file_size > MAX_MEMBER:
                    raise ContractError("vendor_input_invalid")
                total += info.file_size
                if total > MAX_TOTAL:
                    raise ContractError("vendor_input_invalid")
                data = archive.read(info)
                if len(data) != info.file_size or hashlib.sha256(data).hexdigest() != digest:
                    raise ContractError("vendor_input_invalid")
                members[key] = data
            return members
    except ContractError:
        raise
    except Exception:
        raise ContractError("vendor_input_invalid") from None


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _check_local_references(node, root):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise ContractError("nonlocal_reference")
            cursor = root
            for part in ref[2:].split("/"):
                cursor = cursor[part.replace("~1", "/").replace("~0", "~")]
        for child in node.values():
            _check_local_references(child, root)
    elif isinstance(node, list):
        for child in node:
            _check_local_references(child, root)


class _Document:
    def __init__(self, key: str, raw: bytes):
        _, _, operation, path = MEMBERS[key]
        document = yaml.safe_load(raw)
        if document.get("openapi") != OPENAPI_VERSION:
            raise ContractError("unsupported_contract")
        _check_local_references(document, document)
        uri = "urn:bankinghub:" + key
        registry = Registry().with_resource(
            uri, Resource.from_contents(document, default_specification=DRAFT4))  # no retriever
        post = document["paths"][path]["post"]
        if post.get("operationId") != operation:
            raise ContractError("unsupported_operation")
        root = uri + "#/paths/" + _escape(path) + "/post"
        self.key, self.path, self.document = key, path, document
        self.request = OAS30WriteValidator(
            {"$ref": root + "/requestBody/content/application~1json/schema"},
            registry=registry, format_checker=OAS30WriteValidator.FORMAT_CHECKER)
        self.responses = {}
        for status in post["responses"]:
            self.responses[str(status)] = OAS30ReadValidator(
                {"$ref": root + "/responses/" + _escape(str(status))
                 + "/content/application~1json/schema"},
                registry=registry, format_checker=OAS30ReadValidator.FORMAT_CHECKER)
        # The header parameter is declared as a string holding "Serialized JSON
        # representing EFXHeaderObject". The component's declared type differs
        # between members (object in one, string in others), so we check the
        # decoded object against its properties and required list, ignoring
        # only that root type. Nested properties, including the optional
        # Context object, are checked against the member's own local schemas.
        header = document["components"]["schemas"]["EFXHeader"]
        self.header_required = tuple(header.get("required", ()))
        self.header_schema = {
            "type": "object", "required": list(self.header_required),
            "properties": {name: dict(spec) for name, spec in header["properties"].items()},
            "components": document["components"],  # resolves the local "#/components/..." refs
        }


class BankingHubContract:
    """Pinned request/response validators for four generic release operations.

    This validates wire shape only; it does not certify provider behaviour.
    """

    def __init__(self, members: dict[str, bytes]):
        try:
            if set(members) != set(MEMBERS):
                raise ContractError("missing_contract")
            self._documents = {key: _Document(key, raw) for key, raw in members.items()}
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_contract") from None

    @classmethod
    def from_path(cls, path: Path | None = None) -> "BankingHubContract":
        return cls(load_members(path))

    def path(self, key: str) -> str:
        return self._documents[key].path

    def schema(self, key: str, name: str):
        """A named component, for tests that pin a known defect in the release."""
        return self._documents[key].document["components"]["schemas"].get(name)

    def validate_request(self, key: str, body) -> None:
        try:
            self._documents[key].request.validate(body)
        except Exception:
            raise ContractError("invalid_request") from None

    def validate_response(self, key: str, status: int, body) -> None:
        try:
            document = self._documents[key]
            validator = document.responses.get(str(status), document.responses.get("default"))
            if validator is None:
                raise ContractError("invalid_response")
            validator.validate(body)
        except Exception:
            raise ContractError("invalid_response") from None

    def validate_header(self, key: str, header_value: str) -> dict:
        """The JSON-in-header encoding: a JSON object serialized as a string."""
        try:
            document = self._documents[key]
            if not isinstance(header_value, str) or len(header_value) > 4096:
                raise ValueError()
            header = json.loads(header_value)
            if not isinstance(header, dict):
                raise ValueError()
            from jsonschema import Draft4Validator
            Draft4Validator(document.header_schema).validate(header)
            return header
        except Exception:
            raise ContractError("invalid_header") from None
