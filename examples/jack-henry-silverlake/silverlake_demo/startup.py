# SPDX-License-Identifier: MIT
"""Check local prerequisites without starting a service or contacting a provider."""
from __future__ import annotations

import argparse
from importlib.metadata import version
import os
from pathlib import Path
import sys
import tempfile
import tomllib

KEYS = {
    "RASA_LICENSE": "Get a free Developer Edition license at https://rasa.com/developer-edition . Save the full license as RASA_LICENSE.",
    "OPENAI_API_KEY": "Create an API project key at https://platform.openai.com/api-keys and check its API billing. A ChatGPT subscription does not supply this key.",
    "DEEPGRAM_API_KEY": "Create a project API key at https://console.deepgram.com/ . This example uses Deepgram for speech recognition and replies.",
}


def safe_error_type(error):
    allowed = {"ValueError", "RuntimeError", "TimeoutError", "ConnectionError", "OSError",
               "FileNotFoundError", "PermissionError", "ImportError", "ModuleNotFoundError",
               "PackageNotFoundError", "TOMLDecodeError", "ContractError", "MissingContractInput",
               "VendorChanged", "CalledProcessError", "HTTPError", "URLError"}
    name = type(error).__name__
    return name if name in allowed else "ProviderError"


def failure_hint(error):
    return ("Not ready (" + safe_error_type(error) + "). Run make doctor and correct the named prerequisite. "
            "If doctor passes, check the service connection and preserve the local transfer journal before "
            "restarting. Do not repeat a transfer with an uncertain result.")


def locked_rasa(project):
    packages = tomllib.loads((Path(project) / "uv.lock").read_text())["package"]
    selected = [p["version"] for p in packages if p["name"] == "rasa-pro"]
    if len(selected) != 1:
        raise ValueError("expected one locked Rasa package")
    return selected[0]


def check_vendor(project):
    from .contract import ARCHIVE_NAME, SilverLakeContract, VendorChanged
    from .compat import changed_operations
    # The normal loader's compatibility rules apply, including compatible newer
    # archives. Keep its extraction cache temporary: doctor creates no journal.
    with tempfile.TemporaryDirectory(prefix="silverlake-doctor-") as temporary:
        contract = SilverLakeContract.from_path(
            Path(project) / "vendor-inputs" / ARCHIVE_NAME, Path(temporary) / "schema")
        if contract.newer_archive and changed_operations(contract):
            raise VendorChanged(("used operation changed",))
        return contract.newer_archive


def doctor(project, environ=None, output=None, vendor_check=None, installed_version=None):
    from .contract import ARCHIVE_NAME, DOWNLOAD_URL
    environ = os.environ if environ is None else environ
    output = sys.stdout if output is None else output
    ok = True
    for name, hint in KEYS.items():
        present = bool(environ.get(name, "").strip())
        print(name + (": SET (value not checked with provider)" if present else ": MISSING"), file=output)
        if not present:
            ok = False
            print("  " + hint, file=output)
    if not all(environ.get(name, "").strip() for name in KEYS):
        print("Save these names at https://github.com/settings/codespaces and grant RasaHQ/rasa-community-resources access. Stop and restart this Codespace after a secret changes. Never paste values into source or chat.", file=output)
    label = "vendor-inputs/" + ARCHIVE_NAME
    try:
        newer = (check_vendor if vendor_check is None else vendor_check)(project)
        print(label + (": COMPATIBLE NEWER FILE" if newer else ": FOUND AND CHECKED"), file=output)
    except Exception as error:
        ok = False
        print(label + ": NOT READY (" + safe_error_type(error) + ")", file=output)
        print("  Download the public Jack Henry archive from " + DOWNLOAD_URL + ". Run make download to save and check the tested file. For a newer file, follow Vendor files and versions in README.md; never bypass an incompatible-operation refusal.", file=output)
    try:
        expected = locked_rasa(project)
        actual = (version if installed_version is None else installed_version)("rasa-pro")
        if actual != expected:
            raise ValueError("runtime differs from lock")
        print("rasa-pro: MATCHES LOCK " + expected, file=output)
    except Exception as error:
        ok = False
        print("rasa-pro: NOT READY (" + safe_error_type(error) + "). Run make setup to install this folder's locked environment.", file=output)
    print("Ready to start with make run." if ok else "Not ready. Correct the named items, then run make doctor again. No assistant or bank service was started.", file=output)
    return 0 if ok else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["doctor"])
    parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    try:
        from dotenv import load_dotenv
        load_dotenv(project / ".env", override=False)
        return doctor(project)
    except Exception as error:
        print(failure_hint(error))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
