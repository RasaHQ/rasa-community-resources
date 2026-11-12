# SPDX-License-Identifier: MIT
"""Model snapshot bindings must load without the live project on sys.path."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class SnapshotIsolationTests(unittest.TestCase):
    def test_real_sdk_snapshot_loads_all_seven_bindings_without_live_source(self):
        source = Path(__file__).resolve().parents[1]
        probe = r'''
import json
from pathlib import Path
import sys
import sysconfig
import tempfile
source = Path(sys.argv[1]).resolve()
assert sys.flags.isolated
assert not Path.cwd().is_relative_to(source)
# uv installs the locked environment inside project/.venv. Its exact SDK
# site-packages directories remain legitimate under -I; source roots do not.
installed_sites = {Path(sysconfig.get_path(kind)).resolve() for kind in ("purelib", "platlib")}
def live_source_paths():
    return [Path(p).resolve() for p in sys.path if p
        and Path(p).resolve().is_relative_to(source)
        and Path(p).resolve() not in installed_sites]
assert not live_source_paths(), live_source_paths()
# Negative controls: permitting installed packages must not permit source or lib.
for forbidden in (source, source / "lib"):
    sys.path.append(str(forbidden))
    assert forbidden in live_source_paths(), forbidden
    sys.path.pop()
assert not live_source_paths(), live_source_paths()
assert "lib.native_adapter" not in sys.modules
from rasa.mantle.model_archive.snapshot import populate_snapshot
from rasa.mantle.skills.catalog import load_skill_catalog
from rasa.mantle.tools.loader import load_tools_for_skill_catalog
with tempfile.TemporaryDirectory() as temp:
    snapshot = Path(temp) / "snapshot"
    populate_snapshot(snapshot, source, source / "agent.yml")
    bindings = load_tools_for_skill_catalog(load_skill_catalog(snapshot), snapshot / "skills")
    expected = {"banking_accounts", "banking_balance", "banking_history",
        "banking_loan_payment", "banking_payoff", "banking_review_transfer", "banking_transfer_status"}
    assert set(bindings["banking"]) == expected, bindings
    adapter = sys.modules["lib.native_adapter"]
    assert Path(adapter.__file__).is_relative_to(snapshot)
    assert Path(sys.modules["lib.host_client"].__file__).is_relative_to(snapshot)
    print(json.dumps({"isolated": True, "bindings": sorted(expected), "sourceImport": False}))
'''
        environment = {key: value for key, value in os.environ.items() if key != "PYTHONPATH"}
        with tempfile.TemporaryDirectory() as cwd:
            result = subprocess.run([sys.executable, "-I", "-c", probe, str(source)],
                cwd=cwd, env=environment, text=True, capture_output=True, timeout=60)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"sourceImport": false', result.stdout)
