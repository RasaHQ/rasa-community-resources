#!/bin/sh
# Real gate run, scripted mode only. Contains no secret.
# WHAT RUNS
#   1. ./demo setup: uv sync --project project --locked --python 3.12. Installs the locked project environment (rasa-pro
#      3.21.0.dev5 and dependencies) from PyPI into examples/mantle-factory-agent/project/.venv. uv may also download a
#      managed Python 3.12 and fill its own cache.
#   2. Prints which no-network wrapper the machine proves (macOS sandbox-exec, or Linux unshare, sudo -n unshare, or bubblewrap).
#      sudo -n may be tried on Linux. If no wrapper passes, for example when a codespace allows no network namespace, the
#      result is NOT_READY. That means the gate refused to judge, not that anything failed.
#   3. test_isolation.py: 11 refusal tests (fake wrappers, an edited helper, LIVE off Linux).
#   4. test_factory_gate.py: factory_gate.run_factory('good') and ('ignores-limit') in SCRIPTED mode. A scripted builder writes
#      an attempt into a temp folder, then the pinned protected gate (ch06 run_a6.py plus acceptance suite, sha256-pinned)
#      judges it under the no-network wrapper. Expected: good = ACCEPT, ignores-limit = REJECT naming
#      test_b1_four_currencies_show_at_most_the_limit. Two LIVE tests are skipped on Linux by design. No LIVE build is run.
# READS: this checkout, and PyPI during step 1. No credential is read or needed. The tests use the string
#   'unit-test-placeholder' and patched commands, not a provider.
# WRITES: examples/mantle-factory-agent/project/.venv, uv's cache and possibly a managed Python, and temporary folders
#   under $TMPDIR.
# NEEDS: a disposable Linux codespace created from this branch (Python 3.12, uv, network for step 1), or a Mac with
#   sandbox-exec. Do not run it on a machine you share.
# NOT COVERED: any LIVE or funded run, Studio, Mantle in the Inspector.
set -eu
cd "$(dirname "$0")"
./demo setup
project/.venv/bin/python -B -c "import factory_gate; print('wrapper proven:', factory_gate._isolation().first_blocking())"
project/.venv/bin/python -B -m unittest discover -s . -p 'test_isolation.py' -v
project/.venv/bin/python -B -m unittest discover -s . -p 'test_factory_gate.py' -v
