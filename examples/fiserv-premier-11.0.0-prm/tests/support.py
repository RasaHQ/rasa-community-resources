"""Shared test helpers. Vendor-dependent tests skip when the download is absent."""
from pathlib import Path
import socket
import unittest

from premier_demo.contract import MissingContractInput, PremierContract, default_path


def load_contract():
    try:
        return PremierContract.from_path()
    except MissingContractInput:
        raise unittest.SkipTest("vendor definitions not supplied: contract-dependent tests skipped "
                                "(CI is vendor-free; skipped input never qualifies a gate)")


def listener():
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    sock.listen(16)
    return sock


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


EXAMPLE = Path(__file__).resolve().parents[1]
