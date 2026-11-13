# SPDX-License-Identifier: MIT
"""Load the learner-supplied Fiserv Banking Hub (Premier) definitions.

The vendor ZIP is never bundled, fetched or relicensed here. The learner
downloads it by hand; this module checks the whole archive hash, then reads
only the five pinned members, with hard size limits, and builds request and
response validators from those bytes. If the archive differs from the pinned
one, it validates the example's own recorded traffic (recorded_exchanges.py)
against the new files with those same validators: all valid, the example runs
and says so; anything rejected, it stops and names the operation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

import yaml
from jsonschema import Draft4Validator
from jsonschema.exceptions import best_match
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
TESTED_WITH = "Fiserv Banking Hub Premier 11.0.0_PRM specifications as downloaded 12 Nov 2026"  # VENDOR-FILES.md
_MAX_HOPS = 64
# sha256 of reply_schema() for each pinned document: the reply of the one status
# code the client reads (SUCCESS, or "default" if that status is not declared),
# references inlined, with only description, example(s) and summary removed. A
# newer file must give exactly the same digest, because a relaxed reply (a field
# no longer required, nullable, a wider enum or type) would still accept the
# recorded replies yet send the example something it was never tested with.
REPLY_SHA256 = {
    "party": "b2fccab727f3f17b4c915f6c952397044eaeca7cbdd9169329197d781f014307",
    "dda": "f96e1aa79f1b82b16a4d63e4c7833c872843b33278f66edb1f8f89de3d70f409",
    "loan": "e0588b3cff91020572fd4c7b980687736043d0d00dfeb41e4debd4738c41aad0",
    "trn": "605634a2e267583c778b766efd3507ecbe9b8b7b67d96c3cfcccdad3a7e6b1e5",
    "xfer": "6e6e4a9a308f2b40855d693d60f40434a39ebcdf01a2f8162dcee2e5b04fe17b",
}
_DOC_ONLY = frozenset({"description", "example", "examples", "summary"})
_NAME_MAPS = frozenset({"properties", "patternProperties"})  # maps of field names to schemas


class ContractError(Exception):
    """Closed, redacted failure; never carries vendor content or parser text."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


class VendorChanged(ContractError):
    """The supplied Fiserv archive no longer accepts this example's recorded traffic.

    Each change names the operation and the validator's message, which may quote
    a schema value from the vendor file (for example an allowed enum value)."""

    def __init__(self, changes):
        self.changes = tuple(changes)
        super().__init__("vendor_changed: " + "; ".join(self.changes))


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
    # A different archive hash alone does not stop the example: the pinned members
    # are checked below, and a changed member is checked for what this example uses.
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
            gone = [name for name, _, _, _ in MEMBERS.values() if name not in by_name]
            if gone:
                raise VendorChanged(sorted(set(name.rsplit("/", 1)[-1] + " is no longer in the archive"
                                               for name in gone)))
            for key, (name, digest, _, _) in MEMBERS.items():
                info = by_name.get(name)
                if info.file_size > MAX_MEMBER:
                    raise ContractError("vendor_input_invalid")
                total += info.file_size
                if total > MAX_TOTAL:
                    raise ContractError("vendor_input_invalid")
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise ContractError("vendor_input_invalid")
                members[key] = data
            return members
    except ContractError:
        raise
    except Exception:
        raise ContractError("vendor_input_invalid") from None


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _pointer(document, reference):
    if not isinstance(reference, str) or not reference.startswith("#/"):
        raise ContractError("nonlocal_reference")
    value = document
    for part in reference[2:].split("/"):
        value = value[part.replace("~1", "/").replace("~0", "~")]
    return value


def _check_local_references(node, root):
    if isinstance(node, dict):
        if "$ref" in node:
            ref = node["$ref"]
            if not isinstance(ref, str) or not ref.startswith("#/"):
                raise ContractError("nonlocal_reference")
            # A chain of references that only point at further references, and comes
            # back to itself, has no schema at its end: refuse it by name.
            seen, target = [], node
            while isinstance(target, dict) and "$ref" in target:
                ref = target["$ref"]
                if not isinstance(ref, str) or not ref.startswith("#/"):
                    raise ContractError("nonlocal_reference")
                if ref in seen or len(seen) > _MAX_HOPS:
                    raise ContractError("schema_reference_cycle: " + str(node["$ref"]))
                seen.append(ref)
                target = root
                for part in ref[2:].split("/"):
                    target = target[part.replace("~1", "/").replace("~0", "~")]
        for child in node.values():
            _check_local_references(child, root)
    elif isinstance(node, list):
        for child in node:
            _check_local_references(child, root)


def _inline(node, document, stack=(), depth=0):
    """node with every local $ref replaced by its target, documentation removed."""
    if depth > 200:
        raise ContractError("schema_too_deep")
    if isinstance(node, dict):
        if "$ref" in node:
            reference = node["$ref"]
            if reference in stack:  # a recursive schema: name the loop, do not unroll it
                return {"$recursive": reference}
            target = _inline(_pointer(document, reference), document, stack + (reference,), depth + 1)
            rest = _inline({key: value for key, value in node.items() if key != "$ref"},
                           document, stack, depth + 1)
            return {"$inlined": target, **rest} if rest else target
        inlined = {}
        for key, value in sorted(node.items()):
            if key in _NAME_MAPS and isinstance(value, dict):
                # Keys here are field names, not annotations: keep every one, even a
                # field called "description" or "example".
                inlined[key] = {name: _inline(schema, document, stack, depth + 1)
                                for name, schema in sorted(value.items())}
            elif key not in _DOC_ONLY:
                inlined[key] = _inline(value, document, stack, depth + 1)
        return inlined
    if isinstance(node, list):
        return [_inline(value, document, stack, depth + 1) for value in node]
    return node


def reply_schema(key: str, document: dict) -> str:
    """sha256 of the resolved reply the client reads for this document."""
    responses = document["paths"][MEMBERS[key][3]]["post"]["responses"]
    status = SUCCESS[key] if SUCCESS[key] in responses else "default"
    replies = {status: _inline(responses.get(status), document)}
    return hashlib.sha256(json.dumps(replies, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


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
        self.reply = reply_schema(key, document)
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
        self.newer_files = ()  # members whose bytes differ from the pins but stay compatible
        try:
            if set(members) != set(MEMBERS):
                raise ContractError("missing_contract")
            drifted = tuple(key for key, (_, digest, _, _) in MEMBERS.items()
                            if hashlib.sha256(members[key]).hexdigest() != digest)
            self._documents = {}
            for key, raw in members.items():
                try:
                    self._documents[key] = _Document(key, raw)
                except (KeyError, TypeError, ContractError) as error:
                    _, _, operation, path = MEMBERS[key]
                    moved = not isinstance(error, ContractError) or str(error) == "unsupported_operation"
                    if key in drifted and moved:
                        raise VendorChanged([f"{operation} ({key}) is no longer at {path}"]) from None
                    raise
            if drifted:
                problems = [f"the reply of {MEMBERS[key][2]} ({key}) changed; review it and record a new version"
                            for key in MEMBERS if self._documents[key].reply != REPLY_SHA256[key]]
                problems += self.exchange_problems()
                if problems:
                    raise VendorChanged(problems)
                self.newer_files = drifted
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
        from .recorded_exchanges import EXCHANGES
        problems = []
        try:
            for key, side, status, body in EXCHANGES:
                document = self._documents[key]
                operation = MEMBERS[key][2]
                if side == "header":
                    errors = Draft4Validator(document.header_schema).iter_errors(json.loads(body))
                    label = f"{operation} ({key}) EFXHeader"
                    instance = json.loads(body)
                elif side == "request":
                    errors = document.request.iter_errors(body)
                    label = f"{operation} ({key}) request"
                    instance = body
                else:
                    label = f"{operation} ({key}) {status} response"
                    validator = document.responses.get(str(status))
                    if validator is None:
                        problems.append(f"{label} is no longer declared")
                        continue
                    errors = validator.iter_errors(body)
                    instance = body
                error = best_match(errors)
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

    @classmethod
    def from_path(cls, path: Path | None = None) -> "PremierContract":
        contract = cls(load_members(path))
        try:
            archive = hashlib.sha256((path or default_path()).read_bytes()).hexdigest()
        except OSError:
            raise ContractError("vendor_input_unreadable") from None
        contract.newer_archive = archive != ARCHIVE_SHA256
        return contract

    newer_archive = False

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
