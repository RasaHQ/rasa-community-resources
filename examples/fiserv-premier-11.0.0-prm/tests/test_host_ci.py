"""The host, guard and journal tests, run in CI with a vendor-free test double."""
import unittest

from tests import test_flow
from tests.fakes import FakeFixture


class HostWithoutVendorFile(test_flow.HostTests):
    @classmethod
    def setUpClass(cls):
        cls.contract = None  # nothing here needs the vendor file

    def build(self, fault="none"):
        original = test_flow.Fixture
        test_flow.Fixture = FakeFixture
        try:
            return super().build(fault)
        finally:
            test_flow.Fixture = original



if __name__ == "__main__":
    unittest.main()
