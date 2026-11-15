"""Ctrl+C and a plain terminate mean stop; they are never reported as a failed service."""
import os
import signal
import unittest

from premier_demo import launcher


class StopHandlerTests(unittest.TestCase):
    def setUp(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            self.addCleanup(signal.signal, number, signal.getsignal(number))

    def test_ctrl_c_and_terminate_raise_a_keyboard_interrupt_and_set_the_flag(self):
        for number in (signal.SIGINT, signal.SIGTERM):
            launcher.install_stop_handlers()
            self.assertFalse(launcher.stopped_by_the_caller())
            with self.assertRaises(KeyboardInterrupt):
                os.kill(os.getpid(), number)
            self.assertTrue(launcher.stopped_by_the_caller())

    def test_installing_again_clears_the_flag(self):
        launcher.install_stop_handlers()
        with self.assertRaises(KeyboardInterrupt):
            os.kill(os.getpid(), signal.SIGINT)
        launcher.install_stop_handlers()
        self.assertFalse(launcher.stopped_by_the_caller())


if __name__ == "__main__":
    unittest.main()
