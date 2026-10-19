"""Use the actual canonical byte validator across the Python-version boundary."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess

from .turns import MAX_BYTES, Refused


class CanonicalRefusal(Refused):
    """The canonical validator explicitly refused this document (exit 2)."""


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
        if len(raw) > MAX_BYTES:
            raise Refused("response_bound")
        result = subprocess.run(
            self._command, input=raw, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, timeout=5, check=False,
            env=self._environment,
        )
        if result.returncode == 2:
            raise CanonicalRefusal("canonical_validator_refused")
        if result.returncode or len(result.stdout) > MAX_BYTES:
            raise RuntimeError("canonical_validator_unavailable")
        # Only normalized output of the canonical validator reaches the view.
        return json.loads(result.stdout)
