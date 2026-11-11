from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'jack-henry-banking'))
import native_checks as checks


class BankingFlows(checks.NativeFlowTests):
    PROJECT = Path(__file__).resolve().parents[1]


class VoiceRequests(checks.VoiceRequestTests):
    PROJECT = Path(__file__).resolve().parents[1]


class Launcher(checks.LauncherTests):
    PROJECT = Path(__file__).resolve().parents[1]


if __name__ == '__main__':
    unittest.main()
