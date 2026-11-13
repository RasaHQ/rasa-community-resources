#!/usr/bin/env python3
"""Daily check that each bank example still fits the vendor files learners download.

Three steps, run per example by .github/workflows/vendor-drift.yml:

  download <example>  fetch the official files into examples/<example>/vendor-inputs/
                      (ignored by Git, never committed) with the standard library;
  check <example>     inside the example's own locked environment, run the example's
                      own start-up compatibility check and write a JSON result;
  report <example>    turn the result into an issue title and body (with a
                      ready-to-paste CHANGELOG entry), or nothing when unchanged.

A result is one of: "same" (the files are the ones the example was tested with),
"compatible" (they differ, but everything the example uses is unchanged),
"changed" (something it uses changed; named), "unreadable" (the files cannot be
read the way the example expects) or "download_failed". Only "same" is quiet.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "vendor-drift-results"

SYMITAR = "https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/"
EXAMPLES = {
    "jack-henry-symitar": {
        "vendor": "Jack Henry",
        "files": {f"{SYMITAR}{name}/{name}.yaml": f"vendor-inputs/{name}/{name}.yaml"
                  for name in ("accounts", "transactions", "loans", "transfers")},
    },
    "jack-henry-silverlake": {
        "vendor": "Jack Henry",
        "files": {"https://jkhy.github.io/devrel-assets/cms-files/soap/TPG_R2026.1.00_XSD.zip":
                  "vendor-inputs/TPG_R2026.1.00_XSD.zip"},
    },
    "fiserv-premier-11.0.0-prm": {
        "vendor": "Fiserv",
        "files": {"https://developer.fiserv.com/api/download-api-zip/openapi/BankingHub"
                  "?filename=BankingHub_Premier_api_specs.zip&branch=main":
                  "vendor-inputs/BankingHub_Premier_api_specs.zip"},
    },
}
MAX_BYTES = 16 * 1024 * 1024
KNOWN = {"same", "compatible", "changed", "unreadable", "download_failed"}


def _code(text) -> str:
    """Vendor- or network-supplied text, shown literally in a public issue."""
    return "`" + str(text).replace("`", "'").replace("\n", " ")[:300] + "`"


def _result_path(example: str) -> Path:
    return RESULTS / (example + ".json")


def _write(example: str, result: dict) -> None:
    RESULTS.mkdir(exist_ok=True)
    _result_path(example).write_text(json.dumps(result, indent=1, sort_keys=True))


def download(example: str, opener=urllib.request.urlopen) -> dict:
    """Fetch every file; record hashes, or the first failure. Never raises."""
    folder = ROOT / "examples" / example
    hashes = {}
    for url, relative in EXAMPLES[example]["files"].items():
        target = folder / relative
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "rasa-community-vendor-drift"})
            with opener(request, timeout=60) as reply:
                data = reply.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES:
                raise ValueError("file larger than expected")
        except Exception as error:  # a failed check is reported, never taken for "no change"
            result = {"status": "download_failed", "file": relative, "url": url,
                      "detail": type(error).__name__ + ": " + str(error)[:200]}
            _write(example, result)
            return result
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        hashes[relative] = hashlib.sha256(data).hexdigest()
    result = {"status": "downloaded", "hashes": hashes}
    _write(example, result)
    return result


def _check_symitar() -> dict:
    from contract_inputs import TESTED_WITH, ContractError, SymitarContract, VendorChanged, load_inputs
    try:
        contract = SymitarContract(load_inputs())
    except VendorChanged as error:
        return {"status": "changed", "changes": list(error.changes), "tested_with": TESTED_WITH}
    except ContractError as error:
        return {"status": "unreadable", "detail": str(error)[:200], "tested_with": TESTED_WITH}
    status = "compatible" if contract.newer_files else "same"
    return {"status": status, "files": list(contract.newer_files), "tested_with": TESTED_WITH}


def _check_silverlake() -> dict:
    from silverlake_demo.contract import TESTED_WITH, ContractError, SilverLakeContract, VendorChanged
    try:
        contract = SilverLakeContract.from_path()
        changed = []
        if contract.newer_archive:
            from silverlake_demo.compat import changed_operations
            changed = changed_operations(contract)
    except VendorChanged as error:
        return {"status": "changed", "changes": list(error.changes), "tested_with": TESTED_WITH}
    except ContractError as error:
        return {"status": "unreadable", "detail": str(error)[:200], "tested_with": TESTED_WITH}
    if changed:
        return {"status": "changed", "changes": changed, "tested_with": TESTED_WITH}
    return {"status": "compatible" if contract.newer_archive else "same", "tested_with": TESTED_WITH}


def _check_premier() -> dict:
    from premier_demo.contract import TESTED_WITH, ContractError, PremierContract, VendorChanged
    try:
        contract = PremierContract.from_path()
    except VendorChanged as error:
        return {"status": "changed", "changes": list(error.changes), "tested_with": TESTED_WITH}
    except ContractError as error:
        return {"status": "unreadable", "detail": str(error)[:200], "tested_with": TESTED_WITH}
    differs = contract.newer_archive or bool(contract.newer_files)
    return {"status": "compatible" if differs else "same", "files": list(contract.newer_files),
            "tested_with": TESTED_WITH}


CHECKS = {"jack-henry-symitar": _check_symitar, "jack-henry-silverlake": _check_silverlake,
          "fiserv-premier-11.0.0-prm": _check_premier}


def check(example: str) -> dict:
    """Run inside examples/<example> with its locked environment (cwd on sys.path)."""
    previous = json.loads(_result_path(example).read_text()) if _result_path(example).exists() else {}
    if previous.get("status") == "download_failed":
        return previous
    sys.path.insert(0, str(ROOT / "examples" / example))
    try:
        result = CHECKS[example]()
    except Exception as error:  # the example's own check failed to run: report it
        result = {"status": "unreadable", "detail": type(error).__name__ + ": " + str(error)[:200]}
    result["hashes"] = previous.get("hashes", {})
    _write(example, result)
    return result


def report(example: str, today: str | None = None):
    """(title, body) for an issue, or None when the files are unchanged."""
    path = _result_path(example)
    result = json.loads(path.read_text()) if path.exists() else {"status": "no result recorded"}
    status = result.get("status")
    if status == "same":
        return None
    today = today or _dt.date.today().strftime("%d %b %Y").lstrip("0")
    vendor = EXAMPLES[example]["vendor"]
    folder = f"examples/{example}"
    hashes = "\n".join(f"- `{name}`: `{digest}`" for name, digest in sorted(result.get("hashes", {}).items()))
    tested = result.get("tested_with", "the version in VENDOR-FILES.md")
    if status == "download_failed":
        title = f"Vendor drift: could not check {example}"
        body = (f"The daily check could not download `{result['file']}` from {result['url']} "
                f"({_code(result['detail'])}).\n\nThis is not a \"no change\" result: the files were not checked "
                f"today. If it repeats, the example's download route needs attention.")
        return title, body
    if status not in KNOWN:
        title = f"Vendor drift: could not check {example}"
        body = ("The files were downloaded, but the compatibility check did not run or did not finish "
                f"(last recorded step: {_code(status)}). See the workflow run's log.\n\nThis is not a "
                "\"no change\" result: the files were not checked today.")
        return title, body
    title = f"Vendor drift: {vendor} files changed for {example}"
    if status == "compatible":
        verdict = (f"The downloaded files differ from the ones this example was tested with ({tested}), "
                   "but the start-up check found everything the example uses unchanged. The example still "
                   "starts. Update the pins and VENDOR-FILES.md within a day.")
        effect = "none detected by the start-up shape check."
    elif status == "changed":
        changes = "\n".join("- " + change for change in result.get("changes", []))
        verdict = (f"Something this example uses changed since {tested}. The example now stops at start-up "
                   f"for learners who download today's files:\n\n{changes}")
        effect = "affected: " + "; ".join(result.get("changes", [])) + "."
    else:
        verdict = (f"The downloaded files cannot be read the way this example expects "
                   f"({_code(result.get('detail', 'no detail'))}). The example stops at start-up.")
        effect = "affected: the files cannot be read as expected."
    body = f"""{verdict}

**Downloaded today** (sha256):
{hashes or '- (none recorded)'}

**Draft CHANGELOG entry** for `{folder}/CHANGELOG.md` (fill in what changed in plain words):

```markdown
### {today}: files as downloaded {today}

- What changed in the files: (operations, fields, enums or status codes added, removed or changed)
- Effect on this example: {effect}
- What we changed: (new pins, and any code change)
```

Then add a new row to `{folder}/VENDOR-FILES.md` (keep the old rows) and open one small PR with the new pins and tests green."""
    return title, body


def main(argv):
    command, example = argv[1], argv[2]
    if example not in EXAMPLES:
        raise SystemExit("unknown example: " + example)
    if command == "download":
        print(json.dumps(download(example)))
    elif command == "check":
        print(json.dumps(check(example)))
    elif command == "report":
        issue = report(example)
        out = Path(os.environ.get("DRIFT_ISSUE_DIR", RESULTS))
        out.mkdir(exist_ok=True)
        if issue is None:
            print("unchanged: no issue")
            (out / (example + ".none")).write_text("")
        else:
            (out / (example + ".title")).write_text(issue[0])
            (out / (example + ".body")).write_text(issue[1])
            print(issue[0])
    else:
        raise SystemExit("usage: vendor_drift.py download|check|report <example>")


if __name__ == "__main__":
    main(sys.argv)
