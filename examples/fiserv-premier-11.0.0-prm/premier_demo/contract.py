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
TESTED_WITH = "Fiserv Banking Hub Premier 11.0.0_PRM specifications as downloaded 12 Nov 2026"  # VENDOR-FILES.md
# Everything this example sends to or reads from each pinned document. A path
# segment "x[]" is the items of array x.
USED = {
    "party": {"sends": ("PartyAcctRelSel.PartyKeys.PartyId", "RecCtrlIn.MaxRecLimit"),
              "reads": ("Status.Severity", "PartyAcctRelRec[].PartyAcctRelKeys.AcctKeys.AcctId",
                        "PartyAcctRelRec[].PartyAcctRelKeys.AcctKeys.AcctType")},
    "dda": {"sends": ("AcctSel.AcctKeys.AcctId", "AcctSel.AcctKeys.AcctType"),
            "reads": ("AcctRec.DepositAcctInfo.AcctBal[].BalType", "AcctRec.DepositAcctInfo.AcctBal[].CurAmt.Amt",
                      "AcctRec.DepositAcctInfo.AcctBal[].CurAmt.CurCode.CurCodeValue")},
    "trn": {"sends": ("AcctTrnSel.AcctKeys.AcctId", "AcctTrnSel.AcctKeys.AcctType", "AcctTrnSel.TrnPostType",
                      "RecCtrlIn.Cursor"),
            "reads": ("AcctTrnRec[].AcctTrnInfo.PostedDt", "AcctTrnRec[].AcctTrnInfo.DrCrType",
                      "AcctTrnRec[].AcctTrnInfo.TrnAmt.Amt", "AcctTrnRec[].AcctTrnInfo.TrnAmt.CurCode.CurCodeValue",
                      "RecCtrlOut.Cursor")},
    "loan": {"sends": ("AcctSel.AcctKeys.AcctId", "AcctSel.AcctKeys.AcctType"),
             "reads": ("AcctRec.LoanAcctInfo.NextPmt.PmtDt",
                       "AcctRec.LoanAcctInfo.NextPmt.PmtCompositeAmt[].CompositeCurAmtType",
                       "AcctRec.LoanAcctInfo.NextPmt.PmtCompositeAmt[].CurAmt.Amt",
                       "AcctRec.LoanAcctInfo.NextPmt.PmtCompositeAmt[].CurAmt.CurCode.CurCodeValue",
                       "AcctRec.LoanAcctInfo.AcctBal[].BalType", "AcctRec.LoanAcctInfo.AcctBal[].CurAmt.Amt",
                       "AcctRec.LoanAcctInfo.AcctBal[].CurAmt.CurCode.CurCodeValue")},
    "xfer": {"sends": ("XferInfo.TransferType", "XferInfo.FromAcctRef.AcctKeys.AcctId",
                       "XferInfo.FromAcctRef.AcctKeys.AcctType", "XferInfo.ToAcctRef.AcctKeys.AcctId",
                       "XferInfo.ToAcctRef.AcctKeys.AcctType", "XferInfo.CurAmt.Amt",
                       "XferInfo.CurAmt.CurCode.CurCodeType", "XferInfo.CurAmt.CurCode.CurCodeValue"),
             "reads": ("XferStatusRec.XferStatus.XferStatusCode",)},
}
# sha256 of used_surface() for the pinned members. Each used field is recorded by
# its whole schema (every validation keyword, refs inlined, allOf/oneOf/anyOf
# kept; only documentation keys such as description and example are left out),
# plus the operation, path, the required lists around sent fields and the own
# rules of every container passed on the way to a used field. Any
# difference stops start-up. It cannot see a change of meaning that keeps the shape.
USED_SURFACE_SHA256 = "b4d6e005242c4b1d32fc9603481cb11b337a1516745391ff81577a3b50a10073"


class ContractError(Exception):
    """Closed, redacted failure; never carries vendor content or parser text."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


class VendorChanged(ContractError):
    """Something this example uses changed in the supplied Fiserv archive."""

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


def _container(node, document):
    """A container passed on the way to a used field: every keyword except its
    children (properties, items) and documentation. Sibling fields the example
    does not use are left out; the container's own rules (additionalProperties,
    minItems, maxItems, nullable, ...) are kept."""
    own = {key: value for key, value in node.items() if key not in ("properties", "items", "required")}
    return _canonical(own, document)


def _walk(schema, path, document, required_trail, containers):
    """The unresolved schema of the field at path. Records the required list of each
    object passed (for sent fields) and every container's own rules (both directions)."""
    node, raw = _resolve(schema, document), schema
    for token in [t for t in path.split(".") if t]:
        name, is_items = (token[:-2], True) if token.endswith("[]") else (token, False)
        if name:
            containers.append(_container(node, document))
            if required_trail is not None:
                required_trail.append(sorted(node.get("required", [])))
            properties = node.get("properties", {})
            if name not in properties:
                return None
            raw = properties[name]
            node = _resolve(raw, document)
        if is_items:
            containers.append(_container(node, document))
            if "items" not in node:
                return None
            raw = node["items"]
            node = _resolve(raw, document)
    return raw


def used_surface(documents: dict) -> dict:
    """Exactly what this example relies on, from the parsed pinned documents."""
    surface = {}
    for key, (_, _, operation_id, path) in MEMBERS.items():
        document = documents.get(key)
        post = (document or {}).get("paths", {}).get(path, {}).get("post")
        if not isinstance(post, dict) or post.get("operationId") != operation_id:
            surface[key] = "missing"
            continue
        entry = {"path": path, "operation": operation_id, "sends": {}, "required": [], "reads": {}, "containers": {}}
        request = post.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
        for field in USED[key]["sends"]:
            trail, containers = [], []
            node = _walk(request, field, document, trail, containers) if request is not None else None
            entry["sends"][field] = _describe(node, document) if node is not None else "missing"
            entry["required"].append(trail)
            entry["containers"]["sends " + field] = containers
        status = SUCCESS[key]
        schema = post.get("responses", {}).get(status, {}).get("content", {}).get("application/json", {}).get("schema")
        entry["reads"][status] = "present" if schema is not None else "missing"
        for field in USED[key]["reads"]:
            containers = []
            node = _walk(schema, field, document, None, containers) if schema is not None else None
            entry["reads"][field] = _describe(node, document) if node is not None else "missing"
            entry["containers"]["reads " + field] = containers
        surface[key] = entry
    return surface


def surface_digest(surface: dict) -> str:
    return hashlib.sha256(json.dumps(surface, sort_keys=True).encode()).hexdigest()


def _changes(expected: dict, actual: dict) -> list:
    changes = []
    for key in sorted(USED):
        old, new = expected.get(key), actual.get(key)
        if old == new:
            continue
        name = MEMBERS[key][2] + " (" + key + ")"
        if not isinstance(new, dict):
            changes.append(name + " is no longer in its document")
            continue
        for side in ("sends", "reads"):
            for field in sorted(set(old.get(side, {})) | set(new.get(side, {}))):
                if old.get(side, {}).get(field) != new.get(side, {}).get(field):
                    changes.append(f"{name} {'request' if side == 'sends' else 'response'} field {field} changed")
        if old.get("required") != new.get("required"):
            changes.append(name + " now requires different request fields")
        for field in sorted(set(old.get("containers", {})) | set(new.get("containers", {}))):
            if old.get("containers", {}).get(field) != new.get("containers", {}).get(field):
                side, path = field.split(" ", 1)
                changes.append(f"{name} {'request' if side == 'sends' else 'response'} structure around {path} changed")
    return changes or ["the operations this example uses changed"]


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
        self.newer_files = ()  # members whose bytes differ from the pins but stay compatible
        try:
            if set(members) != set(MEMBERS):
                raise ContractError("missing_contract")
            drifted = tuple(key for key, (_, digest, _, _) in MEMBERS.items()
                            if hashlib.sha256(members[key]).hexdigest() != digest)
            if drifted:
                surface = used_surface({key: yaml.safe_load(raw) for key, raw in members.items()})
                if surface_digest(surface) != USED_SURFACE_SHA256:
                    from .used_surface_expected import EXPECTED
                    raise VendorChanged(_changes(EXPECTED, surface))
                self.newer_files = drifted
            self._documents = {key: _Document(key, raw) for key, raw in members.items()}
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_contract") from None

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
