#!/usr/bin/env python3
"""Unit tests for the catalog tooling.

Stdlib `unittest` only — these must run under a bare `python3`, with no
virtualenv and no network, so `make validate` works on a fresh clone.

The regression cases are drawn from real breakages:
  * a stable pin leaving `prerelease = "allow"` behind (silently permitting
    prerelease resolution for every other dependency)
  * `uv lock` preserving prerelease pins after the allowance is dropped
  * `session.*` in instruction prose, and `if:` nested inside an
    `instructions:` scalar, which the engine does not evaluate
  * prose rewriting gluing a version across a newline

Usage:
    python scripts/test_tooling.py
    python scripts/test_tooling.py -v
"""

from __future__ import annotations

import contextlib
import io
import subprocess
import sys
import tomllib
import unittest
from unittest import mock
from pathlib import Path

_SCRIPTS = Path(__file__).resolve().parent
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))

import lint_repo  # noqa: E402
from migrate_rasa_pro import (  # noqa: E402
    _apply_prerelease_setting,
    _replace_pin,
    rewrite_prerelease_flags,
    rewrite_version_text,
)
import rasa_projects  # noqa: E402
import migrate_rasa_pro  # noqa: E402
from rasa_projects import (  # noqa: E402
    _version_sort_key,
    is_prerelease,
    is_valid_version,
    uv_prerelease_args,
)

PYPROJECT = """\
[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11,<3.14"
dependencies = [
    "rasa-pro==3.19.0.dev5",
    "python-dotenv>=1.0.0",
]

[tool.uv]
prerelease = "allow"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["lib"]
"""


class TestVersionSemantics(unittest.TestCase):
    def test_prerelease_detection(self):
        for version in ("3.19.0.dev5", "3.19.0.dev7", "3.19.0rc1", "3.20.0b1", "3.1.0a2"):
            self.assertTrue(is_prerelease(version), version)
        for version in ("3.19.0", "3.19.1", "3.19.1.post1", "3.9.21"):
            self.assertFalse(is_prerelease(version), version)

    def test_validity(self):
        for version in ("3.19.1", "3.19.0.dev5", "3.19.0rc1"):
            self.assertTrue(is_valid_version(version))
        for version in ("X.Y.Z", "", "latest", "3.19.1-suffix"):
            self.assertFalse(is_valid_version(version))

    def test_ordering_puts_stable_above_its_own_prereleases(self):
        versions = ["3.19.1", "3.19.0.dev7", "3.19.0rc1", "3.19.0", "3.9.21", "3.19.0.dev5"]
        self.assertEqual(
            sorted(versions, key=_version_sort_key),
            ["3.9.21", "3.19.0.dev5", "3.19.0.dev7", "3.19.0rc1", "3.19.0", "3.19.1"],
        )

    def test_uv_flags_track_the_pin(self):
        self.assertEqual(uv_prerelease_args("3.19.0.dev7"), ["--prerelease=allow"])
        self.assertEqual(uv_prerelease_args("3.19.1"), [])


class TestPyprojectRewrite(unittest.TestCase):
    def test_pin_replacement_keeps_file_valid(self):
        text, old, changed = _replace_pin(PYPROJECT, "3.19.1")
        self.assertEqual(old, "3.19.0.dev5")
        self.assertTrue(changed)
        data = tomllib.loads(text)
        self.assertEqual(data["project"]["dependencies"][0], "rasa-pro==3.19.1")
        self.assertEqual(data["project"]["dependencies"][1], "python-dotenv>=1.0.0")

    def test_stable_pin_drops_the_prerelease_table(self):
        text, note = _apply_prerelease_setting(PYPROJECT, "3.19.1")
        self.assertIn("removed", note)
        self.assertNotIn("prerelease", text)
        data = tomllib.loads(text)
        self.assertNotIn("uv", data.get("tool", {}))
        # Neighbouring tables must survive the surgery.
        self.assertEqual(data["build-system"]["build-backend"], "hatchling.build")
        self.assertEqual(data["tool"]["hatch"]["build"]["targets"]["wheel"]["packages"], ["lib"])

    def test_prerelease_pin_restores_the_switch(self):
        stable, _ = _apply_prerelease_setting(PYPROJECT, "3.19.1")
        restored, note = _apply_prerelease_setting(stable, "3.20.0.dev1")
        self.assertEqual(note, "added")
        data = tomllib.loads(restored)
        self.assertEqual(data["tool"]["uv"]["prerelease"], "allow")
        self.assertEqual(data["build-system"]["build-backend"], "hatchling.build")

    def test_idempotent(self):
        for version in ("3.19.1", "3.20.0.dev1"):
            once, _ = _apply_prerelease_setting(PYPROJECT, version)
            twice, note = _apply_prerelease_setting(once, version)
            self.assertEqual(once, twice)
            self.assertIsNone(note)


class TestProseRewrite(unittest.TestCase):
    def test_rewrites_the_documented_forms(self):
        text = (
            "Verified with: rasa-pro 3.19.0.dev5, Python 3.11+, uv\n"
            "Pin: `rasa-pro==3.19.0.dev5`.\n"
            "## Notes for Rasa 3.19.0.dev5\n"
            "make migrate VERSION=3.19.0.dev5\n"
            "echo '3.19.0.dev5' > RASA_PRO_VERSION\n"
        )
        out, changed = rewrite_version_text(text, "3.19.0.dev5", "3.19.1")
        self.assertTrue(changed)
        self.assertNotIn("3.19.0.dev5", out)
        self.assertEqual(out.count("3.19.1"), 5)

    def test_never_spans_a_newline(self):
        """A trailing 'rasa-pro' must not absorb a version from the next line."""
        text = "install rasa-pro\n3.19.0.dev5 is the old pin\n"
        out, changed = rewrite_version_text(text, "3.19.0.dev5", "3.19.1")
        self.assertEqual(out, text)
        self.assertFalse(changed)

    def test_leaves_template_placeholders_alone(self):
        text = "Verified with: rasa-pro X.Y.Z, Python 3.11+, uv\n"
        out, changed = rewrite_version_text(text, None, "3.19.1")
        self.assertEqual(out, text)
        self.assertFalse(changed)


class TestPrereleaseFlagRewrite(unittest.TestCase):
    CASES = (
        "\t$(UV) sync --prerelease=allow\n",
        "make install   # uv sync --prerelease=allow\n",
        "| `make install` | Install deps (`uv sync --prerelease=allow`) |\n",
        "uv lock --prerelease=allow\n",
        "\t$(UV) sync\n",
    )

    def test_stable_removes_flag(self):
        for case in self.CASES:
            self.assertNotIn("--prerelease", rewrite_prerelease_flags(case, "3.19.1"))

    def test_prerelease_adds_flag_exactly_once(self):
        for case in self.CASES:
            out = rewrite_prerelease_flags(case, "3.20.0.dev1")
            self.assertEqual(out.count("--prerelease=allow"), 1, out)

    def test_idempotent_both_directions(self):
        for version in ("3.19.1", "3.20.0.dev1"):
            for case in self.CASES:
                once = rewrite_prerelease_flags(case, version)
                self.assertEqual(rewrite_prerelease_flags(once, version), once)


class TestSkillProseExtraction(unittest.TestCase):
    """The lint rule that would have caught the dev5 -> dev7 content break."""

    def _prose(self, text: str) -> str:
        return "\n".join(line for _, line in lint_repo._prose_lines(text))

    def test_frontmatter_is_not_prose(self):
        text = (
            "---\n"
            "name: File Claim\n"
            "tool_constraints:\n"
            "  - submit_claim:\n"
            "      requires: session.file_claim.details_verified\n"
            "---\n"
            "\nBody text.\n"
        )
        prose = self._prose(text)
        self.assertNotIn("session.file_claim.details_verified", prose)
        self.assertIn("Body text.", prose)

    def test_top_level_if_is_a_condition(self):
        text = "---\nname: X\n---\n\nif: session.book.visit_reason == \"urgent\"\nKeep it short.\n"
        prose = self._prose(text)
        self.assertNotIn("session.book.visit_reason", prose)
        self.assertIn("Keep it short.", prose)

    def test_block_yaml_fields_are_not_prose(self):
        """complete_when folded scalars and parameters bindings are evaluated."""
        text = (
            "---\nname: X\n---\n\n"
            ":::ordered_block id=b\n"
            "steps:\n"
            "  - id: confirm_stock\n"
            "    execute_tool: check_availability\n"
            "    parameters:\n"
            "      model: session.reserve_car.requested_model\n"
            "  - id: collect\n"
            "    complete_when: >\n"
            "      (session.file_claim.policy_name == \"Homeowner\") or\n"
            "      (session.file_claim.incident_time)\n"
            ":::\n"
        )
        prose = self._prose(text)
        self.assertNotIn("session.reserve_car.requested_model", prose)
        self.assertNotIn("session.file_claim.policy_name", prose)

    def test_instructions_scalar_is_prose(self):
        text = (
            "---\nname: X\n---\n\n"
            ":::ordered_block id=b\n"
            "steps:\n"
            "  - id: collect_auto\n"
            "    instructions: |\n"
            "      if: session.file_claim.policy_name == \"Car\"\n"
            "      Ask for the incident time.\n"
            "    complete_when: session.file_claim.incident_time\n"
            ":::\n"
        )
        prose = self._prose(text)
        # The nested `if:` is NOT evaluated — it is prose, and must be caught.
        self.assertIn("session.file_claim.policy_name", prose)
        self.assertNotIn("session.file_claim.incident_time", prose)

    def test_body_prose_session_reference_is_caught(self):
        text = (
            "---\nname: X\n---\n\n"
            "In the rare case that `session.project.username` is empty, call\n"
            "load_customer_profile first.\n"
        )
        self.assertIn("session.project.username", self._prose(text))


class TestSkillProseRules(unittest.TestCase):
    def test_session_regex_matches_two_level_refs_only(self):
        self.assertTrue(lint_repo.SESSION_REF_RE.search("session.project.username"))
        self.assertIsNone(lint_repo.SESSION_REF_RE.search("session.project"))
        # A longer dotted path must not be picked up mid-chain.
        self.assertIsNone(lint_repo.SESSION_REF_RE.search("a.session.project.username"))

    def test_incomplete_memory_tokens(self):
        complete = lint_repo.MEMORY_TOKEN_RE.findall("use @memory.project.username here")
        self.assertEqual([t.count(".") for t in complete], [2])
        partial = lint_repo.MEMORY_TOKEN_RE.findall("use @memory.project here")
        self.assertEqual([t.count(".") for t in partial], [1])


class TestLintChecksAgainstRepo(unittest.TestCase):
    """Sanity: the real repository must satisfy every check."""

    def test_repo_is_clean(self):
        from rasa_projects import discover_projects, read_expected_version

        expected = read_expected_version()
        projects = discover_projects()
        self.assertTrue(projects, "no projects discovered")
        errors = [
            f
            for name, fn in lint_repo.CHECKS.items()
            for f in fn(projects, expected)
            if f.severity == lint_repo.SEVERITY_ERROR
        ]
        self.assertEqual(errors, [], "\n".join(f"{f.location()}: {f.message}" for f in errors))



class TestEngineProbe(unittest.TestCase):
    """The capability probe that decides whether a release can run this catalog.

    3.19.1 shipped as the newest rasa-pro while every resource here imports
    `rasa.calm_v2`, which that release does not contain. These cases lock in
    that the probe reads the wheel rather than trusting a hand-written note.
    """

    def _zip_bytes(self, names):
        import io
        import zipfile

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name in names:
                zf.writestr(name, b"x")
        return buf.getvalue()

    def _serve(self, blob, status=200):
        class _Resp:
            status = None

            def __init__(self, data, code):
                self._data = data
                self.status = code

            def read(self):
                return self._data

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        return _Resp(blob, status)

    def test_detects_present_and_absent_module(self):
        with mock.patch.object(
            rasa_projects, "wheel_contents", return_value=["rasa/calm_v2/__init__.py"]
        ):
            self.assertTrue(rasa_projects.release_carries_engine("3.19.0.dev7"))
        with mock.patch.object(
            rasa_projects, "wheel_contents", return_value=["rasa/cli/tools/skills.py"]
        ):
            self.assertFalse(rasa_projects.release_carries_engine("3.19.1"))

    def test_module_match_is_a_package_boundary(self):
        # `rasa/calm_v2_backport/...` must not satisfy a `rasa/calm_v2/` need.
        with mock.patch.object(
            rasa_projects, "wheel_contents", return_value=["rasa/calm_v2_backport/x.py"]
        ):
            self.assertFalse(rasa_projects.release_carries_engine("3.19.1"))

    def test_unranged_response_is_not_padded(self):
        # A server that ignores Range returns 200 and the whole file; padding it
        # would corrupt the archive and turn a real answer into a false negative.
        blob = self._zip_bytes(["rasa/calm_v2/__init__.py"])
        with mock.patch.object(
            rasa_projects,
            "_smallest_wheel",
            return_value={"url": "https://x/y.whl", "size": 10_000_000, "filename": "y.whl"},
        ), mock.patch.object(
            rasa_projects.urllib.request, "urlopen", return_value=self._serve(blob, 200)
        ):
            self.assertIn("rasa/calm_v2/__init__.py", rasa_projects.wheel_contents("3.19.0.dev7"))

    def test_unreadable_archive_is_reported_not_swallowed(self):
        with mock.patch.object(
            rasa_projects,
            "_smallest_wheel",
            return_value={"url": "https://x/y.whl", "size": 0, "filename": "y.whl"},
        ), mock.patch.object(
            rasa_projects.urllib.request, "urlopen", return_value=self._serve(b"not a zip", 200)
        ):
            with self.assertRaises(rasa_projects.IndexUnavailable):
                rasa_projects.wheel_contents("3.19.1")


class TestMigrationEngineGuard(unittest.TestCase):
    """An explicit --version must not walk past the release line."""

    def test_off_line_release_without_engine_is_refused(self):
        with mock.patch.object(
            migrate_rasa_pro, "read_version_line", return_value="3.19.0.dev"
        ), mock.patch.object(
            migrate_rasa_pro, "release_carries_engine", return_value=False
        ):
            with self.assertRaises(SystemExit) as ctx:
                migrate_rasa_pro.verify_engine_support("3.19.1", skip=False)
        self.assertIn("does not ship", str(ctx.exception))

    def test_on_line_release_needs_no_network(self):
        def _boom(*a, **k):  # pragma: no cover - must never run
            raise AssertionError("probed the index for an on-line version")

        with mock.patch.object(
            migrate_rasa_pro, "read_version_line", return_value="3.19.0.dev"
        ), mock.patch.object(migrate_rasa_pro, "release_carries_engine", _boom):
            migrate_rasa_pro.verify_engine_support("3.19.0.dev7", skip=False)

    def test_off_line_release_with_engine_is_allowed(self):
        # Captured: the guard prints an advisory here, and letting it escape
        # makes `make validate` look like it is recommending a version bump.
        buf = io.StringIO()
        with mock.patch.object(
            migrate_rasa_pro, "read_version_line", return_value="3.19.0.dev"
        ), mock.patch.object(
            migrate_rasa_pro, "release_carries_engine", return_value=True
        ), contextlib.redirect_stdout(buf):
            migrate_rasa_pro.verify_engine_support("3.20.0", skip=False)
        self.assertIn("does ship", buf.getvalue())

    def test_probe_failure_refuses_rather_than_guessing(self):
        with mock.patch.object(
            migrate_rasa_pro, "read_version_line", return_value="3.19.0.dev"
        ), mock.patch.object(
            migrate_rasa_pro,
            "release_carries_engine",
            side_effect=migrate_rasa_pro.IndexUnavailable("offline"),
        ):
            with self.assertRaises(SystemExit):
                migrate_rasa_pro.verify_engine_support("3.19.1", skip=False)

    def test_override_skips_every_check(self):
        def _boom(*a, **k):  # pragma: no cover - must never run
            raise AssertionError("probed despite --allow-missing-engine")

        with mock.patch.object(migrate_rasa_pro, "release_carries_engine", _boom):
            migrate_rasa_pro.verify_engine_support("3.19.1", skip=True)


class TestWorkflowPins(unittest.TestCase):
    """Org policy rejects any action not pinned to a full commit SHA."""

    SHA = "11d5960a326750d5838078e36cf38b85af677262"

    def _findings(self, body: str):
        with mock.patch.object(lint_repo, "_tracked_files", return_value=[Path("wf.yml")]), \
             mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_workflow_pins()

    def test_tag_ref_is_rejected(self):
        found = self._findings("      - uses: actions/checkout@v4\n")
        self.assertEqual(len(found), 1)
        self.assertIn("not pinned", found[0].message)

    def test_branch_and_short_sha_are_rejected(self):
        for ref in ("actions/checkout@main", f"actions/checkout@{self.SHA[:7]}"):
            self.assertEqual(len(self._findings(f"      - uses: {ref}\n")), 1, ref)

    def test_full_sha_is_accepted_with_or_without_comment(self):
        for line in (
            f"      - uses: actions/checkout@{self.SHA}\n",
            f"      - uses: actions/checkout@{self.SHA} # v4.4.0\n",
        ):
            self.assertEqual(self._findings(line), [], line)

    def test_local_and_docker_refs_are_exempt(self):
        for ref in ("./.github/actions/setup", "docker://alpine:3.20"):
            self.assertEqual(self._findings(f"      - uses: {ref}\n"), [], ref)

    def test_real_workflows_are_pinned(self):
        self.assertEqual(
            [f.message for f in lint_repo.check_workflow_pins()], []
        )


class TestCliExitCodes(unittest.TestCase):
    """0 = clean, 1 = well-formed request that failed, 2 = bad invocation.

    Only offline paths are asserted here: each of these is rejected during
    argument resolution, before the migrator touches the network.
    """

    def _run(self, *args: str) -> int:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS / "migrate_rasa_pro.py"), *args],
            capture_output=True,
            text=True,
        ).returncode

    def test_malformed_version_is_a_usage_error(self):
        self.assertEqual(self._run("--version", "not-a-version", "--dry-run"), 2)

    def test_mutually_exclusive_selectors(self):
        self.assertEqual(self._run("--latest", "--version", "3.19.1", "--dry-run"), 2)

    def test_argparse_rejects_unknown_flags(self):
        self.assertEqual(self._run("--nope"), 2)

    def test_lint_rejects_unknown_check_name(self):
        rc = subprocess.run(
            [sys.executable, str(_SCRIPTS / "lint_repo.py"), "--check", "nope"],
            capture_output=True, text=True,
        ).returncode
        self.assertEqual(rc, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
