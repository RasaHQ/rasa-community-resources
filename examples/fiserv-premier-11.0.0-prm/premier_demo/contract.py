# SPDX-License-Identifier: MIT
"""Load the learner-supplied Fiserv Banking Hub (Premier) definitions.

The vendor ZIP is never bundled, fetched or relicensed here. The learner
downloads it by hand; this module checks the whole archive hash, then reads
only the five pinned members, with hard size limits, and builds request and
response validators from those exact bytes. A changed upstream file needs
reviewed new pins, never silent acceptance.
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

ARCHIVE_NAME = "BankingHub_Premier_api_specs.zip"
DOWNLOAD_PAGE = "https://developer.fiserv.com/product/BankingHub/api"
ARCHIVE_SHA256 = "65404b27b99d12bedc5cddf5d714dc6117d2d4fb3896e7d18d3067e324f4f7a8"
MAX_ARCHIVE = 8 * 1024 * 1024
MAX_ENTRIES = 512
MAX_MEMBER = 1024 * 1024
MAX_TOTAL = 2 * 1024 * 1024

# document key -> (exact member name, member SHA256, operationId, path)
MEMBERS = {
    "party": ("banking-hub//Premier/Accountholder/PartyAcctRelService-11.0.0_PRM-Inq_ByParty.yaml",
              "c9de4806467223179c0208d7b44781e3b2a8b642f4612664bd356ac2595ceab8",
              "PartyAcctRelInqBySecured", "/partyacctrelservice/partyacctrel/partyacctrel/secured"),
    "dda": ("banking-hub//Premier/Accounts/AcctService-11.0.0_PRM-Inq_DDA.yaml",
            "7f7f5477a7cd9e482857dbf2f2d6780b5fd47abb9ec89a637d61c5a5412d62b4",
            "getAccountsSecured", "/acctservice/acctmgmt/accounts/secured"),
    "loan": ("banking-hub//Premier/Accounts/AcctService-11.0.0_PRM-Inq_LOAN.yaml",
             "55d60b2ab23714821bed9510c9d2d94175bd13ca220bbb9be700490a472569c9",
             "getAccountsSecured", "/acctservice/acctmgmt/accounts/secured"),
    "trn": ("banking-hub//Premier/Transactions/AcctTrnService-11.0.0_PRM-Inq_DDA.yaml",
            "349840d8eba2444fcb0da5fda2512c9c4f524b38550a383dac6174eda7dfe772",
            "AcctTrnInqOperBySecured", "/accttranservice/acctmgmt/acctTrn/secured"),
    "xfer": ("banking-hub//Premier/Transfers/XferService-11.0.0_PRM-Add_Immediate.yaml",
             "2c151366144ff8aae930311ae5a51798b0038e39ef776878ae8bb14b8a16ed99",
             "XferAddOper", "/xferservice/payments/transfers"),
}
SUCCESS = {"party": "200", "dda": "200", "loan": "200", "trn": "200", "xfer": "201"}


class ContractError(Exception):
    """Closed, redacted failure; never carries vendor content or parser text."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


def default_path() -> Path:
    return Path(__file__).resolve().parents[1] / "vendor-inputs" / ARCHIVE_NAME


def load_members(path: Path | None = None) -> dict[str, bytes]:
    """Check the whole archive, then read only the five pinned members."""
    path = path or default_path()
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise MissingContractInput(
            "Vendor definitions not supplied. Download " + ARCHIVE_NAME + " from " + DOWNLOAD_PAGE
            + " (Download API specifications) and save it as vendor-inputs/" + ARCHIVE_NAME
            + " inside the fiserv-premier-11.0.0-prm folder."
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
        if document.get("openapi") != "3.0.1":
            raise ContractError("unsupported_contract")
        _check_local_references(document, document)
        uri = "urn:premier:" + key
        registry = Registry().with_resource(
            uri, Resource.from_contents(document, default_specification=DRAFT4))  # no retriever
        post = document["paths"][path]["post"]
        if post.get("operationId") != operation:
            raise ContractError("unsupported_operation")
        root = uri + "#/paths/" + _escape(path) + "/post"
        self.key, self.path = key, path
        self.request = OAS30WriteValidator(
            {"$ref": root + "/requestBody/content/application~1json/schema"},
            registry=registry, format_checker=OAS30WriteValidator.FORMAT_CHECKER)
        self.responses = {}
        for status in post["responses"]:
            self.responses[str(status)] = OAS30ReadValidator(
                {"$ref": root + "/responses/" + _escape(str(status))
                 + "/content/application~1json/schema"},
                registry=registry, format_checker=OAS30ReadValidator.FORMAT_CHECKER)
        # The vendor declares EFXHeader as type string yet describes object
        # properties. We send it as a JSON string and check the decoded object
        # against the document's own properties and required list.
        header = document["components"]["schemas"]["EFXHeader"]
        self.header_required = tuple(header.get("required", ()))
        self.header_schema = {
            "type": "object", "required": list(self.header_required),
            "properties": {name: dict(spec) for name, spec in header["properties"].items()
                           if name != "Context"},
        }


class PremierContract:
    """Pinned request/response validators, keyed by document, not path alone.

    DDA and LOAN share getAccountsSecured and one path with different schemas.
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
    def from_path(cls, path: Path | None = None) -> "PremierContract":
        return cls(load_members(path))

    def path(self, key: str) -> str:
        return self._documents[key].path

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

    def document_for_account(self, account_type) -> str:
        """Choose the account document from a genuine declared request key."""
        if account_type == "DDA":
            return "dda"
        if account_type == "LOAN":
            return "loan"
        raise ContractError("unsupported_account_type")
