"""Tests for the Studio status and background-start scripts with a fake docker and no network or key."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

HERE = Path(__file__).resolve().parent


def run(script, home, docker_states, env_extra=None):
    """docker_states maps container name -> 'status health' or None for 'no such container'."""
    bin_dir = Path(home) / "bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "fake-start.sh").write_text("exit 0\n")
    cases = "\n".join(f'  {name}) echo "{state}";;' if state else f"  {name}) exit 1;;" for name, state in docker_states.items())
    (bin_dir / "docker").write_text(f'#!/bin/sh\nif [ "$1" = inspect ]; then eval "last=\\${{$#}}"; case "$last" in\n{cases}\n  *) exit 1;; esac; exit 0; fi\nexit 0\n')
    (bin_dir / "docker").chmod(0o755)
    env = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": home, "CODESPACE_NAME": "cs1", "STUDIO_START_SCRIPT": str(bin_dir / "fake-start.sh")}
    env.update(env_extra or {})
    return subprocess.run(["bash", str(HERE / script)], capture_output=True, text=True, env=env, timeout=30)


ALL = ("studio-database", "keycloak", "studio-backend", "studio-web-client", "model-service")
HEALTHY = {n: "running healthy" for n in ALL}


class Status(unittest.TestCase):
    def home(self):
        h = tempfile.mkdtemp(prefix="studio-home-")
        return h

    def test_an_old_ready_marker_does_not_make_studio_ready(self):
        h = self.home()
        Path(h, "studio-start.log").write_text("10:00:00 STUDIO-READY\nStudio: https://old-8080.app.github.dev\n")
        done = run("studio-status.sh", h, {n: None for n in ALL})
        self.assertNotEqual(done.returncode, 0, done.stdout)
        self.assertNotIn("is ready", done.stdout)

    def test_one_unhealthy_container_is_not_ready(self):
        states = dict(HEALTHY, **{"keycloak": "running unhealthy"})
        self.assertNotEqual(run("studio-status.sh", self.home(), states).returncode, 0)

    def test_all_healthy_now_is_ready_and_prints_current_addresses(self):
        done = run("studio-status.sh", self.home(), HEALTHY)
        self.assertEqual(done.returncode, 0, done.stdout)
        self.assertIn("cs1-8080", done.stdout)


class Background(unittest.TestCase):
    def test_an_old_ready_marker_does_not_stop_a_new_start_attempt(self):
        h = tempfile.mkdtemp(prefix="studio-home-")
        Path(h, "studio-start.log").write_text("STUDIO-READY\n")
        done = run("start-studio-background.sh", h, {n: None for n in ALL}, {"RASA_STUDIO_LICENSE": "x"})
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(Path(h, "studio-start.log.prev").exists(), "the old log was not set aside")
        self.assertNotIn("STUDIO-READY", Path(h, "studio-start.log").read_text() if Path(h, "studio-start.log").exists() else "")

    def test_healthy_studio_is_left_alone(self):
        h = tempfile.mkdtemp(prefix="studio-home-")
        done = run("start-studio-background.sh", h, HEALTHY, {"RASA_STUDIO_LICENSE": "x"})
        self.assertIn("already healthy", Path(h, "studio-start.log").read_text())

    def test_the_launch_writes_a_first_line_and_a_pid_and_the_child_survives_the_caller(self):
        import time
        h = tempfile.mkdtemp(prefix="studio-home-")
        done = run("start-studio-background.sh", h, {n: None for n in ALL}, {"RASA_STUDIO_LICENSE": "x"})
        self.assertEqual(done.returncode, 0, done.stderr)
        text = Path(h, "studio-start.log").read_text()
        self.assertIn("postStart ran", text)
        self.assertTrue(Path(h, ".studio-start.pid").read_text().strip().isdigit())
        for _ in range(40):
            if "START-FINISHED" in Path(h, "studio-start.log").read_text():
                break
            time.sleep(0.25)
        self.assertIn("START-FINISHED", Path(h, "studio-start.log").read_text(), "the detached child did not finish after the caller exited")

    def test_no_licence_says_so_and_starts_nothing(self):
        h = tempfile.mkdtemp(prefix="studio-home-")
        run("start-studio-background.sh", h, {n: None for n in ALL})
        self.assertIn("RASA_STUDIO_LICENSE is not set", Path(h, "studio-start.log").read_text())


if __name__ == "__main__":
    unittest.main()
