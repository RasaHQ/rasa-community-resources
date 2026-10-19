"""Use the actual canonical byte validator across the Python-version boundary."""

from __future__ import annotations

import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import time

from .turns import MAX_BYTES, Refused
from .budget import current_budget

VALIDATION_TIMEOUT_SECONDS = 5


class CanonicalRefusal(Refused):
    """The bridge returned its explicit refusal marker and exit code."""


class CoreProcess:
    """Host-configured paths; never accept a command from a model/tool result.

    The caller must first qualify/pin Core and provide a dedicated scratch
    environment. No implicit PATH lookup, dependency install or shared env.
    """

    def __init__(self, python: Path, bridge: Path, *, environment: dict[str, str]):
        if not python.is_absolute() or not bridge.is_absolute():
            raise ValueError("absolute owned interpreter and bridge required")
        self._command = (str(python), "-I", str(bridge))
        self._environment = dict(environment)

    def __call__(self, raw: bytes) -> dict:
        budget = current_budget.get()
        if budget is not None:
            budget.remaining()
        if len(raw) > MAX_BYTES:
            raise Refused("response_bound")
        # A file bounds stdin without blocking on a child that never reads it.
        # Read stdout incrementally: communicate() would buffer without a cap.
        with tempfile.TemporaryFile(dir=self._environment["TMPDIR"]) as source:
            source.write(raw)
            source.seek(0)
            process = subprocess.Popen(
                self._command, stdin=source, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, env=self._environment,
                start_new_session=True,
            )
            output = bytearray()
            deadline = time.monotonic() + VALIDATION_TIMEOUT_SECONDS
            if budget is not None:
                deadline = min(deadline, budget.deadline)
            try:
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while selector.get_map():
                        if budget is not None:
                            budget.remaining()
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise RuntimeError("canonical_validator_timeout")
                        for key, _ in selector.select(min(remaining, 0.05)):
                            chunk = os.read(key.fileobj.fileno(), min(65536, MAX_BYTES + 1 - len(output)))
                            if not chunk:
                                selector.unregister(key.fileobj)
                                continue
                            output.extend(chunk)
                            if len(output) > MAX_BYTES:
                                raise RuntimeError("canonical_validator_output_bound")
                while process.returncode is None:
                    if budget is not None:
                        budget.remaining()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError("canonical_validator_timeout")
                    try:
                        process.wait(timeout=min(remaining, 0.05))
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                # Only our child process group, including any residual descendants.
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=1)
                process.stdout.close()
        if process.returncode == 65 and output == b"ZEO_UI_REFUSED_V1\n":
            raise CanonicalRefusal("canonical_validator_refused")
        if process.returncode:
            raise RuntimeError("canonical_validator_unavailable")
        # Only normalized output of the canonical validator reaches the view.
        return json.loads(output)
