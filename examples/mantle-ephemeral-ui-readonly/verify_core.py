"""Explicit conformance probe; requires the qualified owned Core interpreter.

No skip or substitute validator: absence/refusal of the positive fixture fails.
Run in the supported scratch execution venue, never a borrowed environment.
"""

import argparse
from copy import deepcopy
import json
import os
from pathlib import Path

from lib.core_process import CanonicalRefusal, CoreProcess


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("python", type=Path, help="absolute qualified Core interpreter")
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    validate = CoreProcess(args.python, root / "core_bridge.py", environment={
        key: os.environ[key] for key in (
            "HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"
        ) if key in os.environ
    })
    original = json.loads((root / "fixtures/connection-status.json").read_text())
    raw = json.dumps(original).encode()
    accepted = validate(raw)
    if accepted["schema"] != "zeo.ui-result/v1" or accepted["complete"] is not False:
        raise RuntimeError("positive Core boundary failed")
    cases = {
        "duplicate": raw[:-1] + b',"complete":false}',
        "invalid_utf8": b"\xff",
        "bom": b"\xef\xbb\xbf" + raw,
        "trailing": raw + b" {}",
    }
    for name in ("unknown", "version", "kind", "second_card", "actions", "bad_fact"):
        value = deepcopy(original)
        if name == "unknown":
            value["unexpected"] = True
        elif name == "version":
            value["schema"] = "zeo.ui-result/v2"
        elif name == "kind":
            value["components"][0]["kind"] = "table"
        elif name == "second_card":
            value["components"].append(deepcopy(value["components"][0]))
        elif name == "actions":
            value["components"][0]["props"]["action_refs"] = ["act"]
        else:
            value["components"][0]["props"]["facts"][0]["value_type"] = "integer"
        cases[name] = json.dumps(value).encode()
    for name, invalid in cases.items():
        try:
            validate(invalid)
        except CanonicalRefusal:
            continue
        raise RuntimeError("Core accepted negative vector: " + name)
    print("Core positive and 10 negative vectors passed; synthetic input only.")


if __name__ == "__main__":
    main()
