# SPDX-License-Identifier: MIT
"""Load the learner-supplied Jack Henry jXchange (TPG R2026.1.00) archive.

The archive is never bundled, fetched or relicensed here. The learner downloads
it by hand. This module checks the whole archive hash and its member list,
extracts it into an ignored local cache (bounded, no traversal or links), checks
the two pinned WSDLs, reads each operation's SOAPAction from them, and loads the
Inquiry and Transaction master schemas with local-only resolution. Every SOAP
body in this example is validated against those schemas.
"""
from __future__ import annotations

import hashlib
from pathlib import Path, PurePosixPath
import shutil
import xml.etree.ElementTree as ET
import zipfile

ARCHIVE_NAME = "TPG_R2026.1.00_XSD.zip"
DOWNLOAD_URL = "https://jkhy.github.io/devrel-assets/cms-files/soap/TPG_R2026.1.00_XSD.zip"
ARCHIVE_SHA256 = "a433a01b05925bd9af2bb12184046443574eba98c4fbf65b716b73cad6ff7900"
PREFIX = "R2026.1.00TPGPub/Validation/"
WSDLS = {
    "TPG_Inquiry.wsdl": "f2ff471b945b938ae0173ba2174eeb9fbb30c678c3232f177566bb27143b5108",
    "TPG_Transaction.wsdl": "559ce0113d96260ce4f7437c0dfd3a6ad49c0d976fc29abfdfaa31680dafbd22",
}
TESTED_WITH = "Jack Henry jXchange TPG R2026.1.00 XSD archive as published 3 Nov 2026"  # VENDOR-FILES.md
MAX_ARCHIVE = 4 * 1024 * 1024
MAX_MEMBERS = 64
MAX_EXTRACTED = 16 * 1024 * 1024
NS = "http://jackhenry.com/jxchange/TPG/2008"
SOAP_ENV = "http://schemas.xmlsoap.org/soap/envelope/"
OPERATIONS = {  # operation -> (WSDL, schema family)
    "AcctSrch": ("TPG_Inquiry.wsdl", "inquiry"),
    "AcctBalInq": ("TPG_Inquiry.wsdl", "inquiry"),
    "AcctHistSrch": ("TPG_Inquiry.wsdl", "inquiry"),
    "AcctInq": ("TPG_Inquiry.wsdl", "inquiry"),
    "LnPayoffInq": ("TPG_Inquiry.wsdl", "inquiry"),
    "XferAdd": ("TPG_Transaction.wsdl", "transaction"),
}


class ContractError(Exception):
    """Closed, redacted failure; never carries vendor content or parser text."""


class MissingContractInput(ContractError):
    """Launch stops; contract tests may explicitly skip only this case."""


class VendorChanged(ContractError):
    """Something this example uses changed in the supplied Jack Henry archive."""

    def __init__(self, changes):
        self.changes = tuple(changes)
        super().__init__("vendor_changed: " + "; ".join(self.changes))


def example_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_path() -> Path:
    return example_root() / "vendor-inputs" / ARCHIVE_NAME


def _safe_member(info: zipfile.ZipInfo) -> bool:
    name = info.filename
    parts = PurePosixPath(name).parts
    mode = (info.external_attr >> 16) & 0o170000
    return not (name.startswith("/") or "\\" in name or ".." in parts or mode == 0o120000
                or not name.startswith("R2026.1.00TPGPub/"))


def extract(path: Path | None = None, cache: Path | None = None) -> Path:
    """Check the archive and extract it once into an ignored cache folder."""
    path = path or default_path()
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        raise MissingContractInput(
            "Vendor definitions not supplied. Download " + ARCHIVE_NAME + " from " + DOWNLOAD_URL
            + " and save it as vendor-inputs/" + ARCHIVE_NAME + " inside the jack-henry-silverlake folder."
        ) from None
    if size > MAX_ARCHIVE:
        raise ContractError("vendor_input_invalid")
    raw = path.read_bytes()
    # A different archive hash alone does not stop the example; the operations it
    # uses are checked against the supplied schemas (see compat.py).
    digest = hashlib.sha256(raw).hexdigest()
    cache = cache or example_root() / "var" / "cache" / ("jxchange-" + digest[:16])
    marker = cache / ".complete"
    if not marker.is_file():
        tmp = cache.with_name(cache.name + ".partial")
        shutil.rmtree(tmp, ignore_errors=True)
        try:
            with zipfile.ZipFile(path) as archive:
                infos = archive.infolist()
                if len(infos) > MAX_MEMBERS or sum(i.file_size for i in infos) > MAX_EXTRACTED:
                    raise ContractError("vendor_input_invalid")
                seen = set()
                for info in infos:
                    if not _safe_member(info) or info.filename.casefold() in seen:
                        raise ContractError("vendor_input_invalid")
                    seen.add(info.filename.casefold())
                for info in infos:
                    target = tmp / info.filename
                    if info.is_dir():
                        target.mkdir(parents=True, exist_ok=True)
                        continue
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(info))
        except ContractError:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        except Exception:
            shutil.rmtree(tmp, ignore_errors=True)
            raise ContractError("vendor_input_invalid") from None
        shutil.rmtree(cache, ignore_errors=True)
        tmp.rename(cache)
        marker.write_text(digest)
    folder = cache / PREFIX
    for name in WSDLS:
        if not (folder / name).is_file():
            raise VendorChanged([name + " is no longer in the archive"])
    return folder


def _soap_actions(wsdl: Path) -> dict[str, str]:
    tree = ET.parse(wsdl)  # no DTD processing or network access in ElementTree
    actions = {}
    wsdl_ns = "{http://schemas.xmlsoap.org/wsdl/}"
    soap_ns = "{http://schemas.xmlsoap.org/wsdl/soap/}"
    for binding in tree.getroot().iter(wsdl_ns + "binding"):
        for operation in binding.iter(wsdl_ns + "operation"):
            soap = operation.find(soap_ns + "operation")
            if soap is not None and soap.get("soapAction"):
                actions[operation.get("name")] = soap.get("soapAction")
    return actions


class SilverLakeContract:
    """Pinned jXchange schemas and SOAPActions. Wire shape only, not provider behaviour."""

    def __init__(self, folder: Path):
        import warnings
        import xmlschema
        import xmlschema.limits
        # The jXchange master schemas nest deeper than the library's default limit.
        xmlschema.limits.MAX_MODEL_DEPTH = max(xmlschema.limits.MAX_MODEL_DEPTH, 200)
        try:
            self.actions = {}
            moved = []
            for operation, (wsdl, _) in OPERATIONS.items():
                found = _soap_actions(folder / wsdl).get(operation)
                if found != "http://jackhenry.com/ws/" + operation:
                    moved.append(operation + " SOAPAction changed or removed")
                self.actions[operation] = found
            if moved:
                raise VendorChanged(moved)
            options = dict(allow="sandbox", defuse="always")
            # The archive's XML-signature schema declares a DTD entity, which we
            # refuse to process; that optional security namespace stays unresolved.
            warnings.filterwarnings("ignore", category=xmlschema.XMLSchemaImportWarning)
            self.schemas = {
                "inquiry": xmlschema.XMLSchema(str(folder / "TPG_InquiryMaster.xsd"), **options),
                "transaction": xmlschema.XMLSchema(str(folder / "TPG_TransactionMaster.xsd"), **options),
            }
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_contract") from None

    @classmethod
    def from_path(cls, path: Path | None = None, cache: Path | None = None) -> "SilverLakeContract":
        path = path or default_path()
        folder = extract(path, cache)
        contract = cls(folder)
        contract.newer_archive = hashlib.sha256(path.read_bytes()).hexdigest() != ARCHIVE_SHA256 or any(
            hashlib.sha256((folder / name).read_bytes()).hexdigest() != digest for name, digest in WSDLS.items())
        return contract

    newer_archive = False

    def schema_for(self, element: str):
        base = element[:-len("Response")] if element.endswith("Response") else element
        if base not in OPERATIONS:
            raise ContractError("unsupported_operation")
        return self.schemas[OPERATIONS[base][1]]

    def validate(self, element: ET.Element) -> None:
        """Validate one body element (request or response) against the pinned XSD."""
        try:
            name = element.tag.split("}", 1)[1] if element.tag.startswith("{" + NS + "}") else None
            if name is None:
                raise ContractError("wrong_namespace")
            schema = self.schema_for(name)
            import xmlschema
            # The instance is in memory: it may not reach any file or network.
            resource = xmlschema.XMLResource(element, allow="none", defuse="always")
            if not schema.is_valid(resource):
                raise ContractError("invalid_body")
        except ContractError:
            raise
        except Exception:
            raise ContractError("invalid_body") from None


def envelope(body: ET.Element) -> bytes:
    env = ET.Element("{%s}Envelope" % SOAP_ENV)
    ET.SubElement(env, "{%s}Header" % SOAP_ENV)
    ET.SubElement(env, "{%s}Body" % SOAP_ENV).append(body)
    return ET.tostring(env, encoding="utf-8", xml_declaration=True)


def open_envelope(raw: bytes) -> ET.Element:
    """Return the single body element, or raise. Refuses DTDs and entities."""
    if not isinstance(raw, bytes) or len(raw) > 262144 or b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ContractError("invalid_envelope")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise ContractError("invalid_envelope") from None
    body = root.find("{%s}Body" % SOAP_ENV)
    if root.tag != "{%s}Envelope" % SOAP_ENV or body is None or len(body) != 1:
        raise ContractError("invalid_envelope")
    return body[0]


def q(name: str) -> str:
    return "{%s}%s" % (NS, name)


def sub(parent: ET.Element, name: str, text: str | None = None) -> ET.Element:
    child = ET.SubElement(parent, q(name))
    if text is not None:
        child.text = text
    return child


def header(parent: ET.Element, search: bool = False, max_rec: int | None = None,
           cursor: str | None = None, response: bool = False) -> ET.Element:
    name = ("SrchMsgRsHdr" if search else "MsgRsHdr") if response else ("SrchMsgRqHdr" if search else "MsgRqHdr")
    hdr = sub(parent, name)
    jx = sub(hdr, "jXchangeHdr")
    sub(jx, "AuditUsrId", "rasa-demo")
    sub(jx, "AuditWsId", "rasa-demo")
    if search and not response:
        sub(hdr, "MaxRec", str(max_rec or 20))
        if cursor:
            sub(hdr, "Cursor", cursor)
    return hdr
