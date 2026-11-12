"""Shared test helpers. Vendor-dependent tests skip when the download is absent."""
import socket
import unittest

from silverlake_demo.contract import MissingContractInput, SilverLakeContract

_CONTRACT = None


def load_contract():
    global _CONTRACT
    if _CONTRACT is None:
        try:
            _CONTRACT = SilverLakeContract.from_path()
        except MissingContractInput:
            raise unittest.SkipTest("SKIP: vendor definitions not supplied (download the jXchange archive; "
                                    "a skipped input never qualifies the contract)")
    return _CONTRACT


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
