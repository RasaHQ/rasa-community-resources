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
import json
import re
import subprocess
import sys
import tempfile
import tomllib
import unittest
from datetime import date, timedelta
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

    def test_historical_assessment_is_preserved_while_installation_advances(self):
        text = "Verified with: rasa-pro 3.20.0.dev6 # rasa-version-ignore: historical assessment\nInstallation: rasa-pro 3.20.0.dev6\n"
        out, changed = rewrite_version_text(text, "3.20.0.dev6", "3.20.0.dev9")
        self.assertTrue(changed)
        self.assertIn("Verified with: rasa-pro 3.20.0.dev6", out)
        self.assertIn("Installation: rasa-pro 3.20.0.dev9", out)

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


class TestStaleDocVersionsIgnoreMarker(unittest.TestCase):
    """A doc line carrying `rasa-version-ignore` may name an old version.

    Without the exemption, the only way an upgrade illustration could pass
    the stale-version scan was to rewrite its FROM side to the current pin,
    which produces degenerate `X → X` prose that teaches nothing — the same
    defect shape RULING-004/F-A caught in a tutorial's landed bytes.
    """

    def _project_with_readme(self, text: str) -> "rasa_projects.Project":
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "README.md").write_text(text, encoding="utf-8")
        return rasa_projects.Project(path=root)

    def test_an_unmarked_stale_mention_is_reported(self):
        project = self._project_with_readme(
            "Upgrade from rasa-pro==3.19.0.dev5 before following along.\n"
        )
        stale = rasa_projects.stale_doc_versions(project, "3.20.0.dev6")
        self.assertEqual(stale, {"README.md": ["3.19.0.dev5"]})

    def test_the_marker_exempts_exactly_its_own_line(self):
        project = self._project_with_readme(
            "rasa-pro==3.19.0.dev5  ->  rasa-pro==3.20.0.dev6"
            "   # rasa-version-ignore: upgrade path\n"
            "This line is still checked: rasa-pro==3.18.0\n"
        )
        stale = rasa_projects.stale_doc_versions(project, "3.20.0.dev6")
        self.assertEqual(stale, {"README.md": ["3.18.0"]})

    def test_a_fully_marked_doc_reports_nothing(self):
        project = self._project_with_readme(
            "was rasa-pro==3.19.0.dev5 <!-- rasa-version-ignore: changelog -->\n"
        )
        stale = rasa_projects.stale_doc_versions(project, "3.20.0.dev6")
        self.assertEqual(stale, {})


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


class TestFictionalDataPolicy(unittest.TestCase):
    """The fictional-data rules, each with the mutation that turns it red.

    Operator directive 2026-09-02: every person, company and institution in
    catalog content must be invented. These tests hold the mechanical third
    of that policy; the doctrine lives in docs/TUTORIAL-TEMPLATE.md §5.
    """

    def test_a_real_institution_name_is_flagged(self):
        line = "Our client BNP Paribas asked for a document workflow."
        self.assertTrue(lint_repo.REAL_ENTITY_RE.search(line))

    def test_vendor_products_are_not_flagged(self):
        for line in (
            "Point HUBSPOT_BASE_URL at the real HubSpot API.",
            "Deepgram Flux for ASR, OpenAI for the judge.",
        ):
            self.assertIsNone(lint_repo.REAL_ENTITY_RE.search(line))

    def test_reserved_and_declared_email_domains_pass(self):
        for addr in ("dana.okafor@example.com", "bel.riose@asimovbranch.com"):
            domain = lint_repo._EMAIL_RE.search(addr).group(1).lower()
            ok = bool(
                lint_repo._RESERVED_EMAIL_RE.search("@" + domain)
            ) or domain in lint_repo.FICTIONAL_EMAIL_DOMAINS
            self.assertTrue(ok, addr)

    def test_an_unreserved_email_domain_is_flagged(self):
        domain = lint_repo._EMAIL_RE.search("ceo@barclays-wealth.co.uk").group(1)
        self.assertFalse(lint_repo._RESERVED_EMAIL_RE.search("@" + domain))
        self.assertNotIn(domain.lower(), lint_repo.FICTIONAL_EMAIL_DOMAINS)

    def test_fixture_readme_must_carry_a_fiction_token(self):
        self.assertTrue(
            lint_repo.FICTION_TOKEN_RE.search("All records here are invented.")
        )
        self.assertIsNone(
            lint_repo.FICTION_TOKEN_RE.search(
                "Records for the pilot deployment."  # the red mutation: a
                # README that exists but never says the data is fictional
            )
        )

    def test_the_full_check_is_clean_on_the_real_repo_and_bites_on_a_probe(self):
        """End to end: clean now; a planted real-entity file turns it red."""
        clean = [
            f for f in lint_repo.check_fictional_data()
            if f.severity == lint_repo.SEVERITY_ERROR
        ]
        self.assertEqual(clean, [], "\n".join(f.message for f in clean))
        probe = lint_repo.REPO_ROOT / "examples" / "_fiction_probe.md"
        probe.write_text("A case study with JPMorgan private bank.\n")
        try:
            subprocess.run(
                ["git", "-C", str(lint_repo.REPO_ROOT), "add", str(probe)],
                check=True, capture_output=True,
            )
            hits = [
                f for f in lint_repo.check_fictional_data()
                if "JPMorgan" in f.message
            ]
            self.assertTrue(hits, "planted real institution was not flagged")
        finally:
            subprocess.run(
                ["git", "-C", str(lint_repo.REPO_ROOT), "rm", "-fq", "--cached", str(probe)],
                check=True, capture_output=True,
            )
            probe.unlink(missing_ok=True)


class TestLintChecksAgainstRepo(unittest.TestCase):
    """Sanity: the real repository must satisfy every check."""

    def test_repo_is_clean(self):
        from rasa_projects import discover_projects, read_expected_version

        expected = read_expected_version()
        projects = discover_projects()
        snapshots = discover_projects("snapshots")
        self.assertTrue(projects, "no projects discovered")
        errors = [
            f
            for name, fn in lint_repo.CHECKS.items()
            for f in fn(projects, snapshots, expected)
            if f.severity == lint_repo.SEVERITY_ERROR
        ]
        self.assertEqual(errors, [], "\n".join(f"{f.location()}: {f.message}" for f in errors))



class TestEngineProbe(unittest.TestCase):
    """The capability probe that decides whether a release can run this catalog.

    3.19.1 shipped as the newest rasa-pro while every resource here imports
    `rasa.mantle`, which that release does not contain. These cases lock in
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


class TestApiKeyEnv(unittest.TestCase):
    """Model-group credentials: `api_key: ${VAR}` only; `api_key_env` rejected.

    rasa-pro 3.21.0.dev2 removed `api_key_env` and requires every sensitive
    value to be exactly `${ENV_VAR_NAME}` (rasa/shared/providers/
    model_group_validation.py). The 3.21.0.dev3 release run failed
    validate_project 22 times on the removed key while `make validate` stayed
    green. These tests exist so the check is known to FAIL on each rejected
    form, not merely known to pass on the accepted one.
    """

    def _findings(self, body: str, name: str = "integrations.yml"):
        with mock.patch.object(
            lint_repo, "_tracked_files", return_value=[Path(name)]
        ), mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_api_key_env()

    def test_api_key_env_is_rejected(self):
        found = self._findings("        api_key_env: OPENAI_API_KEY\n")
        self.assertEqual(len(found), 1)
        self.assertIn("removed in rasa-pro 3.21.0.dev2", found[0].message)
        self.assertIn("api_key: ${VAR}", found[0].message)

    def test_api_key_env_as_list_item_is_rejected(self):
        self.assertEqual(
            len(self._findings("      - api_key_env: OPENAI_API_KEY\n")), 1
        )

    def test_braced_placeholder_is_accepted(self):
        for value in ("${OPENAI_API_KEY}", '"${OPENAI_API_KEY}"', "'${GEMINI_API_KEY}'"):
            self.assertEqual(
                self._findings(f"        api_key: {value}\n"), [], value
            )

    def test_placeholder_with_trailing_comment_is_accepted(self):
        self.assertEqual(
            self._findings("        api_key: ${OPENAI_API_KEY}  # from .env\n"), []
        )

    def test_every_other_value_is_rejected(self):
        # The engine's pattern is fullmatch `\${(\w+)}`; anything else fails.
        for value in (
            "$OPENAI_API_KEY",
            '"$OPENAI_API_KEY"',
            "${OPENAI_API_KEY:-none}",
            "OPENAI_API_KEY",
            "sk-not-a-real-key",
            "",
        ):
            found = self._findings(f"        api_key: {value}\n")
            self.assertEqual(len(found), 1, repr(value))
            self.assertIn("must be exactly '${VAR}'", found[0].message)

    def test_non_sensitive_placeholder_is_left_alone(self):
        self.assertEqual(self._findings("        model: ${OPENAI_MODEL}\n"), [])

    def test_commented_out_line_is_left_alone(self):
        self.assertEqual(self._findings("      # api_key_env: OPENAI_API_KEY\n"), [])

    def test_prose_quoting_the_removed_form_is_left_alone(self):
        # Documentation must be able to name the removed key in order to
        # explain the migration; only a real mapping entry is a finding.
        body = "Replace `api_key_env: OPENAI_API_KEY` with `api_key: ${OPENAI_API_KEY}`.\n"
        self.assertEqual(self._findings(body, "MIGRATING.md"), [])

    def test_ignore_marker_is_honoured(self):
        body = "        api_key_env: OPENAI_API_KEY  # api-key-env-ignore\n"
        self.assertEqual(self._findings(body, "MIGRATING.md"), [])

    def test_credential_inside_voice_block_is_rejected(self):
        # ASR configs are extra="forbid" and TTS warns-and-ignores; either way
        # the engine reads DEEPGRAM_API_KEY from the environment, not config.
        for key in (
            "api_key_env: DEEPGRAM_API_KEY",
            "api_key: DEEPGRAM_API_KEY",
            "api_key: ${DEEPGRAM_API_KEY}",
        ):
            body = f"asr:\n  deepgram:\n    {key}\n"
            found = self._findings(body)
            self.assertEqual(len(found), 1, key)
            self.assertIn("not read by the engine", found[0].message)

    def test_voice_block_ends_at_dedent(self):
        # A model-group `api_key` after a tts: block is correct, not a
        # voice-block finding — the block must not swallow the rest of the file.
        body = (
            "channels:\n"
            "  inspector:\n"
            "    tts:\n"
            "      name: deepgram\n"
            "model_groups:\n"
            "  - models:\n"
            "      - api_key: ${OPENAI_API_KEY}\n"
        )
        self.assertEqual(self._findings(body), [])

    def test_catalog_is_clean(self):
        self.assertEqual([f.location() for f in lint_repo.check_api_key_env()], [])


class TestStarterPackApiKeyEnv(unittest.TestCase):
    """starter-pack/scripts/lint_mantle.py enforces the same credential rule.

    The starter pack ships this lint into other people's projects as a
    pre-commit hook, so it has to agree with the catalog gate and the engine.
    """

    @classmethod
    def setUpClass(cls):
        import importlib.util

        path = _SCRIPTS.parent / "starter-pack" / "scripts" / "lint_mantle.py"
        spec = importlib.util.spec_from_file_location("lint_mantle", path)
        cls.lint = importlib.util.module_from_spec(spec)
        # dataclasses resolves the defining module through sys.modules.
        sys.modules[spec.name] = cls.lint
        spec.loader.exec_module(cls.lint)

    def _findings(self, body: str):
        with mock.patch.object(
            self.lint, "_files", return_value=[Path("integrations.yml")]
        ), mock.patch.object(self.lint, "_read", return_value=body):
            return self.lint.check_api_key_env()

    def test_api_key_env_is_rejected(self):
        found = self._findings("        api_key_env: OPENAI_API_KEY\n")
        self.assertEqual(len(found), 1)
        self.assertIn("removed in rasa-pro 3.21.0.dev2", found[0].message)

    def test_braced_placeholder_is_accepted(self):
        self.assertEqual(self._findings("        api_key: ${OPENAI_API_KEY}\n"), [])

    def test_other_values_are_rejected(self):
        for value in ("$OPENAI_API_KEY", "${OPENAI_API_KEY:-x}", "OPENAI_API_KEY", ""):
            self.assertEqual(
                len(self._findings(f"        api_key: {value}\n")), 1, repr(value)
            )

    def test_commented_line_is_left_alone(self):
        self.assertEqual(self._findings("  # api_key_env: OPENAI_API_KEY\n"), [])

    def test_env_example_discovers_the_placeholder_name(self):
        # .env.example discovery must see the variable named inside ${...}.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env.example").write_text("RASA_LICENSE=\n")
            (root / "integrations.yml").write_text(
                "model_groups:\n  - id: o\n    models:\n"
                "      - api_key: ${GEMINI_API_KEY}\n"
            )
            with mock.patch.object(self.lint, "ROOT", root), mock.patch.object(
                self.lint, "_files", return_value=[root / "integrations.yml"]
            ):
                found = self.lint.check_env_example()
        self.assertEqual(len(found), 1)
        self.assertIn("GEMINI_API_KEY", found[0].message)


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


class TestAssessedOnDate(unittest.TestCase):
    """`Assessed on` is timezone-less, so today differs by locale.

    Regression: a README stamped with the author's local date failed CI on a
    UTC runner that had not reached that date yet.
    """

    def _findings(self, assessed: str):
        readme = (
            "```text\n"
            "Author:        A\n"
            f"Assessed on:   {assessed}\n"
            "Assessed by:   A\n"
            "Verified with: rasa-pro 1.0.0, Python 3.11+, uv\n"
            "```\n"
        )
        project = rasa_projects.Project(Path("examples/demo"))
        with mock.patch("pathlib.Path.is_file", return_value=True), \
             mock.patch.object(lint_repo, "_read", return_value=readme):
            return lint_repo.check_resource_metadata([project])

    def test_tomorrow_is_tolerated_as_timezone_skew(self):
        tomorrow = date.today() + timedelta(days=1)
        self.assertEqual(self._findings(tomorrow.isoformat()), [])

    def test_today_and_past_are_fine(self):
        for when in (date.today(), date.today() - timedelta(days=400)):
            self.assertEqual(self._findings(when.isoformat()), [], when)

    def test_genuinely_future_date_is_still_caught(self):
        soon = date.today() + timedelta(days=3)
        found = self._findings(soon.isoformat())
        self.assertEqual(len(found), 1)
        self.assertIn("in the future", found[0].message)

    def test_malformed_date_is_reported(self):
        found = self._findings("2026-13-45")
        self.assertEqual(len(found), 1)
        self.assertIn("not a valid date", found[0].message)


class TestAgentConfigKeys(unittest.TestCase):
    """Prompt-tuning keys belong beside `agent:`, never inside it.

    The regression this locks in: every agent.yml in the catalog nested
    `rules:` under `agent:`. 39 rules were declared and the engine applied
    none — `AgentSpec` is `extra="ignore"` and `_agent_spec_payload` reads
    those keys from the root mapping, so the misplacement is silent at parse,
    train, and load time. Reported independently by Samrudha Kelkar and
    Daksh Varshneya.
    """

    def _findings(self, body: str):
        with mock.patch.object(lint_repo, "_tracked_files", return_value=[Path("agent.yml")]), \
             mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_agent_config_keys()

    NESTED = (
        "agent:\n"
        "  id: demo\n"
        "  persona: |\n"
        "    Be helpful.\n"
        "  rules:\n"
        '    - "Be polite."\n'
    )
    HOISTED = (
        "agent:\n"
        "  id: demo\n"
        "  persona: |\n"
        "    Be helpful.\n"
        "\n"
        "rules:\n"
        '  - "Be polite."\n'
    )

    def test_nested_rules_are_caught(self):
        found = self._findings(self.NESTED)
        self.assertEqual(len(found), 1)
        self.assertIn("'rules'", found[0].message)
        self.assertEqual(found[0].line, 5)

    def test_hoisted_rules_are_clean(self):
        self.assertEqual(self._findings(self.HOISTED), [])

    def test_every_top_level_key_is_covered(self):
        for key in lint_repo.TOP_LEVEL_AGENT_KEYS:
            body = f"agent:\n  id: demo\n  {key}: something\n"
            self.assertEqual(len(self._findings(body)), 1, key)

    def test_identity_keys_are_left_alone(self):
        # id/language/persona/voice genuinely live inside `agent:`; flagging
        # them would send an author to move the one thing that is correct.
        body = (
            "agent:\n"
            "  id: demo\n"
            "  language: en\n"
            "  persona: text\n"
            "  voice:\n"
            "    enabled: true\n"
            "    asr: deepgram\n"
        )
        self.assertEqual(self._findings(body), [])

    def test_four_space_indentation_is_still_checked(self):
        # The check derives the block indent instead of assuming two spaces,
        # so a differently formatted file cannot slip past it.
        body = "agent:\n    id: demo\n    rules:\n" '        - "Be polite."\n'
        self.assertEqual(len(self._findings(body)), 1)

    def test_nested_block_children_are_not_mistaken_for_top_level_keys(self):
        # `description:` inside a `voice:` sub-block is at a deeper indent and
        # is not the agent-level key this check is about.
        body = (
            "agent:\n"
            "  id: demo\n"
            "  voice:\n"
            "    description: inner\n"
            "    enabled: true\n"
        )
        self.assertEqual(self._findings(body), [])

    def test_the_real_catalog_is_clean(self):
        self.assertEqual(
            [f.location() for f in lint_repo.check_agent_config_keys()], []
        )


class TestAgentSpecContract(unittest.TestCase):
    """The check has to keep matching the engine it is protecting.

    If a future rasa-pro moves a key into the `agent:` block, or adds a new
    top-level one, this fails and points at the list to update — rather than
    the check quietly enforcing last year's schema.
    """

    def test_key_list_matches_the_installed_engine(self):
        spec = None
        for venv in Path(".").glob("*/*/.venv/lib/*/site-packages"):
            # The engine package was renamed calm_v2 -> mantle in 3.20. Look
            # for both: pinning one name is how this test silently started
            # skipping after the rename, which is worse than failing.
            for package in ("mantle", "calm_v2"):
                candidate = venv / "rasa" / package / "config" / "agent_spec.py"
                if candidate.is_file():
                    spec = candidate
                    break
            if spec is not None:
                break
        if spec is None:
            self.skipTest("no installed rasa-pro to compare against")
        self.assertTrue(spec.is_file(), spec)

        source = spec.read_text()
        body = source.split("def _agent_spec_payload", 1)[1].split("\ndef ", 1)[0]
        # The keys the payload builder copies straight off the root mapping.
        found = set(re.findall(r'^\s+"(\w+)",$', body, re.M))
        found |= {"conversation", "before_end"}  # copied via _CONVERSATION_KEY/_BEFORE_END_KEY
        self.assertEqual(
            found,
            set(lint_repo.TOP_LEVEL_AGENT_KEYS),
            "rasa-pro's top-level agent.yml keys changed; update "
            "lint_repo.TOP_LEVEL_AGENT_KEYS to match",
        )

# ------------------------------------------------------------------------------
# Two tiers: maintained catalog vs frozen snapshots
# ------------------------------------------------------------------------------


class FakeRepo(contextlib.ContextDecorator):
    """A throwaway repository tree with both REPO_ROOTs pointed at it.

    `lint_repo` imports REPO_ROOT by value, so patching only `rasa_projects`
    would leave `_rel` resolving against the real checkout and silently produce
    absolute paths in findings.
    """

    def __enter__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self._patches = [
            mock.patch.object(rasa_projects, "REPO_ROOT", self.root),
            mock.patch.object(lint_repo, "REPO_ROOT", self.root),
        ]
        for patch in self._patches:
            patch.start()
        return self

    def __exit__(self, *exc):
        for patch in reversed(self._patches):
            patch.stop()
        self._tmp.cleanup()
        return False

    def project(
        self,
        rel,
        *,
        pin="3.19.0.dev5",
        lock=...,
        verified=...,
        prerelease="allow",
        extra_metadata="",
        env_example=True,
    ):
        """Write a minimal resource at `rel`. `...` means "same as pin"."""
        path = self.root / rel
        path.mkdir(parents=True, exist_ok=True)
        table = f'\n[tool.uv]\nprerelease = "{prerelease}"\n' if prerelease else ""
        (path / "pyproject.toml").write_text(
            f'[project]\nname = "demo"\nversion = "0.1.0"\n'
            f'dependencies = [\n    "rasa-pro=={pin}",\n]\n{table}'
        )
        if lock is not None:
            locked = pin if lock is ... else lock
            (path / "uv.lock").write_text(
                f'version = 1\n\n[[package]]\nname = "rasa-pro"\nversion = "{locked}"\n'
            )
        if verified is not None:
            claim = pin if verified is ... else verified
            (path / "README.md").write_text(
                "# Demo\n\n```text\n"
                "Author:        A Contributor\n"
                f"{extra_metadata}"
                f"Assessed on:   {date.today().isoformat()}\n"
                "Assessed by:   A Contributor\n"
                f"Verified with: rasa-pro {claim}, Python 3.11+, uv\n"
                "```\n"
            )
        if env_example:
            (path / ".env.example").write_text("RASA_LICENSE=\n")
        return path

    def index(self, rel, body):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
        return path


class TestTierDiscovery(unittest.TestCase):
    """Which roots are the maintained catalog, and which are frozen."""

    def test_patterns_is_part_of_the_catalog(self):
        # Regression: `patterns/` was absent from SCAN_ROOTS, so the first
        # pattern contributed would have shipped with no lock-sync, no
        # env-example check, and no install job in the CI matrix.
        self.assertIn("patterns", rasa_projects.SCAN_ROOTS)

    def test_community_is_maintained_not_frozen(self):
        # Contributed examples move with the catalog. One pinned to a release
        # the rest of the repository has left behind is one nobody clones.
        self.assertIn("community", rasa_projects.SCAN_ROOTS)
        self.assertNotIn("community", rasa_projects.SNAPSHOT_ROOT_NAMES)

    def test_only_heroes_is_frozen(self):
        self.assertEqual(rasa_projects.SNAPSHOT_ROOT_NAMES, ("heroes",))

    def test_catalog_scope_excludes_frozen_roots(self):
        with FakeRepo() as repo:
            repo.project("examples/agent")
            repo.project("patterns/handoff")
            repo.project("community/handle-thing")
            repo.project("heroes/wave-01-voice/projects/handle-thing")
            catalog = {p.rel for p in rasa_projects.discover_projects()}
            frozen = {p.rel for p in rasa_projects.discover_projects("snapshots")}

        self.assertEqual(
            catalog, {"examples/agent", "patterns/handoff", "community/handle-thing"}
        )
        self.assertEqual(frozen, {"heroes/wave-01-voice/projects/handle-thing"})

    def test_discovered_snapshots_are_flagged_as_such(self):
        with FakeRepo() as repo:
            repo.project("heroes/wave-01-voice/projects/a-thing")
            repo.project("community/handle-thing")
            by_rel = {
                p.rel: p.snapshot for p in rasa_projects.discover_projects("all")
            }
        self.assertEqual(
            by_rel,
            {
                "community/handle-thing": False,
                "heroes/wave-01-voice/projects/a-thing": True,
            },
        )

    def test_wave_depth_is_exact(self):
        # A project filed directly under the wave, rather than under
        # `projects/`, must not be discovered — heroes-layout is what reports
        # it, and it can only do so if discovery has not quietly accepted it.
        with FakeRepo() as repo:
            repo.project("heroes/wave-01-voice/misfiled")
            self.assertEqual(rasa_projects.discover_projects("snapshots"), [])

    def test_unknown_scope_is_rejected(self):
        with self.assertRaises(ValueError):
            rasa_projects.discover_projects("everything")


class TestVersionConsistencyTiers(unittest.TestCase):
    """The shared pin governs everything maintained, and stops at `heroes/`."""

    def _findings(self, tracked):
        with mock.patch.object(lint_repo, "_tracked_files", return_value=tracked):
            return lint_repo.check_version_consistency("3.19.0.dev7")

    def test_catalog_prose_is_held_to_the_pin(self):
        with FakeRepo() as repo:
            readme = repo.project("patterns/handoff", pin="3.19.0.dev5") / "README.md"
            found = self._findings([readme])
        # One `Verified with:` line matches two prose patterns, so the count is
        # not the interesting part — that every finding names the stale version
        # and the catalog file is.
        self.assertTrue(found)
        self.assertTrue(all("3.19.0.dev5" in f.message for f in found), found)
        self.assertEqual({f.path for f in found}, {"patterns/handoff/README.md"})

    def test_community_is_held_to_the_pin_too(self):
        # The point of moving `community/` into the catalog: a contributed
        # resource left on an old pin is a finding, not an accepted state.
        with FakeRepo() as repo:
            project = repo.project("community/a-thing", pin="3.19.0.dev5")
            found = self._findings([project / "README.md", project / "pyproject.toml"])
        self.assertTrue(found)
        self.assertTrue(all("3.19.0.dev5" in f.message for f in found), found)

    def test_wave_prose_is_left_alone(self):
        with FakeRepo() as repo:
            wave = repo.project("heroes/wave-01-voice/projects/a-thing", pin="3.18.0")
            found = self._findings([wave / "README.md", wave / "pyproject.toml"])
        self.assertEqual(found, [])


class TestSnapshotPin(unittest.TestCase):
    """A frozen wave project must be internally honest and reproducible."""

    WAVE = "heroes/wave-01-voice/projects/a-thing"

    def _findings(self):
        return lint_repo.check_snapshot_pins(
            rasa_projects.discover_projects("snapshots")
        )

    def test_consistent_snapshot_is_clean(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, pin="3.19.0.dev5")
            self.assertEqual(self._findings(), [])

    def test_stable_pin_needs_no_prerelease_allowance(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, pin="3.18.0", prerelease=None)
            self.assertEqual(self._findings(), [])

    def test_missing_lock_is_an_error(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, lock=None)
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertIn("missing uv.lock", found[0].message)
        # The fix it suggests must match the pin it saw.
        self.assertIn("--prerelease=allow", found[0].message)

    def test_lock_disagreeing_with_the_pin_is_an_error(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, pin="3.19.0.dev5", lock="3.19.0.dev7")
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertIn("resolved rasa-pro==3.19.0.dev7", found[0].message)

    def test_readme_claiming_another_version_is_an_error(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, pin="3.19.0.dev5", verified="3.18.0")
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertIn("one of the two is wrong", found[0].message)

    def test_prerelease_pin_without_the_allowance_is_an_error(self):
        with FakeRepo() as repo:
            repo.project(self.WAVE, pin="3.19.0.dev5", prerelease="disallow")
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertIn("resolution will fail", found[0].message)


class TestIndexRows(unittest.TestCase):
    """Contributed work no index mentions is work nobody can find.

    Tier-independent on purpose: `community/` is maintained and `heroes/` is
    frozen, but both are flat or cohort-keyed, so a reader browsing the tree
    has nothing to guess from.
    """

    def _findings(self):
        return lint_repo.check_index_rows(rasa_projects.discover_projects("all"))

    def test_listed_resources_are_clean(self):
        with FakeRepo() as repo:
            repo.project("community/handle-thing")
            repo.index("community/README.md", "| [`handle-thing`](handle-thing) |\n")
            repo.project("heroes/wave-01-voice/projects/handle-agent")
            repo.index(
                "heroes/wave-01-voice/README.md",
                "| [`handle-agent`](projects/handle-agent) |\n",
            )
            self.assertEqual(self._findings(), [])

    def test_unlisted_community_resource_is_reported(self):
        with FakeRepo() as repo:
            repo.project("community/handle-thing")
            repo.index("community/README.md", "no rows yet\n")
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].path, "community/README.md")

    def test_wave_project_is_indexed_by_its_wave_not_the_programme(self):
        with FakeRepo() as repo:
            repo.project("heroes/wave-01-voice/projects/handle-agent")
            repo.index("heroes/README.md", "handle-agent\n")   # wrong index
            repo.index("heroes/wave-01-voice/README.md", "no rows yet\n")
            found = self._findings()
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].path, "heroes/wave-01-voice/README.md")

    def test_typed_category_folders_are_not_policed(self):
        # examples/ and patterns/ keep their inventory by review convention; a
        # reader can guess where to look, so this check stays out of them.
        with FakeRepo() as repo:
            repo.project("examples/agent")
            repo.project("patterns/handoff")
            self.assertEqual(self._findings(), [])


class TestHeroesLayout(unittest.TestCase):
    """One shape per wave, so no cohort is half-filed."""

    def _wave(self, repo, slug, *, charter=True, listed=True):
        (repo.root / "heroes" / slug / "projects").mkdir(parents=True, exist_ok=True)
        if charter:
            repo.index(f"heroes/{slug}/README.md", "# Wave\n")
        repo.index("heroes/README.md", f"| {slug} |\n" if listed else "no waves\n")

    def test_well_formed_wave_is_clean(self):
        with FakeRepo() as repo:
            self._wave(repo, "wave-01-voice")
            repo.project("heroes/wave-01-voice/projects/handle-agent")
            self.assertEqual(lint_repo.check_heroes_layout(), [])

    def test_unpadded_slug_is_rejected(self):
        with FakeRepo() as repo:
            self._wave(repo, "wave-1-voice")
            found = lint_repo.check_heroes_layout()
        self.assertEqual(len(found), 1)
        self.assertIn("wave-NN-<theme>", found[0].message)

    def test_missing_charter_is_reported(self):
        with FakeRepo() as repo:
            self._wave(repo, "wave-01-voice", charter=False)
            found = lint_repo.check_heroes_layout()
        self.assertEqual(len(found), 1)
        self.assertIn("missing wave charter", found[0].message)

    def test_wave_absent_from_the_programme_index_is_reported(self):
        with FakeRepo() as repo:
            self._wave(repo, "wave-01-voice", listed=False)
            found = lint_repo.check_heroes_layout()
        self.assertEqual(len(found), 1)
        self.assertIn("does not list", found[0].message)

    def test_project_outside_projects_dir_is_reported(self):
        # This is the failure that matters most: discovery skips it by depth,
        # so without this check it would ship with zero coverage and look fine.
        with FakeRepo() as repo:
            self._wave(repo, "wave-01-voice")
            repo.project("heroes/wave-01-voice/misfiled")
            found = lint_repo.check_heroes_layout()
        self.assertEqual(len(found), 1)
        self.assertIn("skipped by every check", found[0].message)


class TestMigrationLeavesSnapshotsAlone(unittest.TestCase):
    """`make migrate` sweeps the catalog and stops at the frozen tier."""

    def _run_migrate(self, *extra):
        """Call the migrator in-process, offline, with the network gates off."""
        argv = [
            "migrate_rasa_pro.py",
            "--dry-run",
            "--no-index-check",
            "--allow-missing-engine",
            "--version",
            "3.19.0.dev7",
            *extra,
        ]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), contextlib.redirect_stderr(err), \
             contextlib.redirect_stdout(io.StringIO()):
            code = migrate_rasa_pro.main()
        return code, err.getvalue()

    def test_targeting_a_wave_project_is_refused_not_silently_ignored(self):
        frozen = rasa_projects.Project(
            rasa_projects.REPO_ROOT / "heroes" / "wave-01-voice" / "projects" / "a",
            snapshot=True,
        )

        def fake_discover(scope="catalog"):
            return [] if scope == "catalog" else [frozen]

        with mock.patch.object(migrate_rasa_pro, "discover_projects", fake_discover):
            code, err = self._run_migrate(
                "--project", "heroes/wave-01-voice/projects/a"
            )

        # Exit 2 is the "bad invocation" slot, and the message has to say why —
        # "unknown project" would send the contributor off renaming things.
        self.assertEqual(code, 2)
        self.assertIn("Refusing to migrate frozen snapshot", err)

    def test_community_is_in_the_migration_scope(self):
        with FakeRepo() as repo:
            repo.project("community/a-thing")
            self.assertEqual(
                [p.rel for p in rasa_projects.discover_projects()],
                ["community/a-thing"],
            )

    def test_wave_projects_are_not_in_the_migration_scope(self):
        with FakeRepo() as repo:
            repo.project("heroes/wave-01-voice/projects/a-thing")
            self.assertEqual(rasa_projects.discover_projects(), [])


class TestBrandTerms(unittest.TestCase):
    """Retired product names stay retired, in content and in paths.

    The rename that prompted this was not cosmetic: `rasa init --engine <old>`
    was published as a copy-paste instruction in six files while the CLI had
    already narrowed to `--engine {calm,mantle}` and rejected the old value.
    """

    # Assembled, so this file does not trip the check it exercises.
    RETIRED = "ma" + "estro"

    def _content(self, body):
        with mock.patch.object(lint_repo, "_tracked_files",
                               side_effect=lambda *g: [Path("doc.md")] if g else []), \
             mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_brand_terms()

    def _paths(self, paths):
        with mock.patch.object(lint_repo, "_tracked_files",
                               side_effect=lambda *g: [] if g else paths), \
             mock.patch.object(lint_repo, "_read", return_value=""):
            return lint_repo.check_brand_terms()

    def test_retired_name_in_prose_is_caught(self):
        found = self._content(f"This is a Rasa {self.RETIRED.capitalize()} agent.\n")
        self.assertEqual(len(found), 1)
        self.assertIn("Mantle", found[0].message)

    def test_match_is_case_insensitive(self):
        for spelling in (self.RETIRED, self.RETIRED.upper(), self.RETIRED.capitalize()):
            self.assertEqual(len(self._content(spelling + "\n")), 1, spelling)

    def test_clean_text_is_clean(self):
        self.assertEqual(self._content("This is a Rasa Mantle agent.\n"), [])

    def test_retired_name_in_a_path_is_caught(self):
        found = self._paths([Path(f"examples/{self.RETIRED}-voice-agent/README.md")])
        self.assertEqual(len(found), 1)
        self.assertIn("path contains", found[0].message)

    def test_clean_paths_are_clean(self):
        self.assertEqual(self._paths([Path("examples/mantle-voice-agent/README.md")]), [])

    def test_the_real_repository_is_clean(self):
        self.assertEqual([f.location() for f in lint_repo.check_brand_terms()], [])


class TestLlmModelGroup(unittest.TestCase):
    """The orchestrator LLM is a model-group reference, not inline settings.

    Regression: 3.20.0.dev6 made `IntegrationLlmConfig` extra="forbid" with a
    required `model_group`. Every project in the catalog failed
    `validate_project` at once, each with
    `'provider': Extra inputs are not permitted`.
    """

    def _findings(self, body):
        project = rasa_projects.Project(Path("examples/demo"))
        with mock.patch("pathlib.Path.is_file", return_value=True), \
             mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_llm_model_group([project])

    GOOD = (
        "llm:\n"
        "  model_group: orchestrator\n"
        "\n"
        "model_groups:\n"
        "  - id: orchestrator\n"
        "    models:\n"
        "      - provider: openai\n"
        "        model: gpt-5.2\n"
    )

    def test_model_group_reference_is_clean(self):
        self.assertEqual(self._findings(self.GOOD), [])

    def test_inline_provider_is_caught(self):
        body = "llm:\n  provider: openai\n  model: gpt-5.2\n  api_key_env: OPENAI_API_KEY\n"
        found = self._findings(body)
        # Three inline keys, plus the missing model_group itself.
        self.assertEqual(len(found), 4)
        self.assertTrue(any("model_group': Field required" in f.message for f in found))

    def test_missing_model_group_alone_is_caught(self):
        found = self._findings("llm:\n  max_prompt_tokens: 4000\n")
        self.assertEqual(len(found), 1)
        self.assertIn("does not name a model_group", found[0].message)

    def test_provider_inside_model_groups_is_not_flagged(self):
        # `provider:` is correct *under a group* — only inline under `llm:` is wrong.
        self.assertEqual(self._findings(self.GOOD), [])

    def test_commented_inline_form_is_ignored(self):
        body = (
            "llm:\n"
            "  model_group: orchestrator\n"
            "  # provider: openai   <- how it used to look\n"
        )
        self.assertEqual(self._findings(body), [])

    def test_the_real_catalog_uses_model_groups(self):
        projects = rasa_projects.discover_projects("all")
        self.assertEqual(
            [f.location() for f in lint_repo.check_llm_model_group(projects)], []
        )


class TestProjectMemoryWrites(unittest.TestCase):
    """Root memory.yml is tool-written; `llm_settable` belongs to skills.

    Regression: 3.20.0.dev6 started rejecting the flag on project fields, and
    two tutorials carried it inertly until validate_project refused them.
    """

    def _findings(self, body):
        project = rasa_projects.Project(Path("tutorials/demo"))
        with mock.patch("pathlib.Path.is_file", return_value=True), \
             mock.patch.object(lint_repo, "_read", return_value=body):
            return lint_repo.check_project_memory_writes([project])

    def test_llm_settable_project_field_is_caught(self):
        found = self._findings("contact_email:\n  type: text\n  llm_settable: true\n")
        self.assertEqual(len(found), 1)
        self.assertIn("cannot be llm_settable", found[0].message)

    def test_tool_written_project_field_is_clean(self):
        self.assertEqual(self._findings("contact_id:\n  type: text\n"), [])

    def test_llm_settable_false_is_clean(self):
        self.assertEqual(
            self._findings("x:\n  type: text\n  llm_settable: false\n"), []
        )

    def test_commented_flag_is_ignored(self):
        self.assertEqual(
            self._findings("x:\n  type: text\n  # llm_settable: true\n"), []
        )

    def test_the_real_catalog_is_clean(self):
        projects = rasa_projects.discover_projects("all")
        self.assertEqual(
            [f.location() for f in lint_repo.check_project_memory_writes(projects)], []
        )


class TestStaleDocVersionsHonoursIgnoreMarker(unittest.TestCase):
    """`stale_doc_versions` must agree with the lint about marked lines.

    Regression for the gate that was green *because* of a bug: the function
    read each doc as one string, so it never saw `VERSION_IGNORE_MARKER` and
    rejected every honest two-version upgrade path. The only text that
    satisfied it was a degenerate path naming one version twice — the very
    defect the marker exists to avoid. Both directions are asserted: skipping
    marked lines must not turn the check off for unmarked ones.
    """

    EXPECTED = "3.20.0.dev6"

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = rasa_projects.Project(Path(self._tmp.name))

    def _stale(self, body: str) -> dict[str, list[str]]:
        (Path(self._tmp.name) / "README.md").write_text(body, encoding="utf-8")
        return rasa_projects.stale_doc_versions(self.project, self.EXPECTED)

    def test_marked_two_version_upgrade_path_passes(self):
        body = (
            "# Demo\n\nPinned to `rasa-pro==3.20.0.dev6`.\n\n"
            "```bash\n"
            "rasa-pro==3.19.1  →  rasa-pro==3.20.0.dev6"
            "   # rasa-version-ignore: upgrade path\n"
            "```\n"
        )
        self.assertEqual(self._stale(body), {})

    def test_unmarked_stale_version_still_fails(self):
        # The half that matters. Without it, deleting the check outright would
        # leave this suite green.
        body = "# Demo\n\nPinned to `rasa-pro==3.19.1`.\n"
        self.assertEqual(self._stale(body), {"README.md": ["3.19.1"]})

    def test_marker_only_exempts_its_own_line(self):
        # A marked line must not licence a stale version elsewhere in the file.
        body = (
            "rasa-pro==3.19.1  →  rasa-pro==3.20.0.dev6"
            "   # rasa-version-ignore: upgrade path\n"
            "\nElsewhere this doc still claims `rasa-pro==3.18.0`.\n"
        )
        self.assertEqual(self._stale(body), {"README.md": ["3.18.0"]})

    def test_the_two_gates_agree_on_the_marker_constant(self):
        # lint_repo re-exports the constant rather than keeping its own copy;
        # two spellings drifting apart is how this bug happened in the first
        # place.
        self.assertIs(
            lint_repo.VERSION_IGNORE_MARKER, rasa_projects.VERSION_IGNORE_MARKER
        )



class TestCaseBuildHarness(unittest.TestCase):
    """Offline checks for scripts/case_builds/harness.py (no server, no model)."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(_SCRIPTS / "case_builds"))
        import harness

        cls.h = harness

    TRACKER = {
        "events": [
            {"event": "user", "text": "is my policy active?"},
            {"event": "tool_executed", "tool_name": "activate", "arguments": {"target_id": "x"}, "result": "done"},
            {"event": "tool_executed", "tool_name": "get_policy_status",
             "arguments": {"policy_number": "hc-ho-1"},
             "result": '{"status": "answered", "facts": {"subject": true}}', "is_error": False},
            {"event": "bot", "text": "It is active.", "metadata": {"mantle_response_source": "filler"}},
            {"event": "user", "text": "so it's covered?"},
            {"event": "tool_executed", "tool_name": "open_question",
             "arguments": {"policy_number": "HC-HO-1", "loss": "burst pipe"},
             "result": '{"status": "routed", "decision": null}', "is_error": False},
            {"event": "bot", "text": "Only the claims team can say whether it is covered. You're covered!",
             "metadata": {"mantle_response_source": "llm"}},
        ]
    }

    def check(self, check):
        return self.h.evaluate_check(check, self.TRACKER)[0]

    def test_tool_called_matches_args_case_insensitively_and_result_subset(self):
        self.assertTrue(self.check({"type": "tool_called", "tool": "get_policy_status",
                                    "args": {"policy_number": "HC-HO-1"},
                                    "result": {"status": "answered", "facts": {"subject": True}}}))
        self.assertFalse(self.check({"type": "tool_called", "tool": "get_policy_status",
                                     "result": {"status": "blocked"}}))

    def test_after_user_turn_and_order(self):
        self.assertTrue(self.check({"type": "tool_called", "tool": "open_question", "after_user_turn": 1}))
        self.assertFalse(self.check({"type": "tool_called", "tool": "get_policy_status", "after_user_turn": 1}))
        self.assertTrue(self.check({"type": "tool_order", "steps": [{"tool": "get_policy_status"}, {"tool": "open_question"}]}))
        self.assertFalse(self.check({"type": "tool_order", "steps": [{"tool": "open_question"}, {"tool": "get_policy_status"}]}))

    def test_regex_null_any_of_and_not_called(self):
        self.assertTrue(self.check({"type": "tool_called", "tool": "open_question",
                                    "args": {"loss": "re:pipe|flood"}, "result": {"decision": None}}))
        self.assertTrue(self.check({"type": "tool_not_called", "result": {"status": "blocked"}}))
        self.assertFalse(self.check({"type": "tool_not_called", "tool": "open_question"}))
        self.assertTrue(self.check({"type": "any_of", "checks": [
            {"type": "tool_called", "tool": "missing"}, {"type": "no_tool_errors"}]}))

    def test_engine_tools_are_separated_and_turns_counted(self):
        calls = self.h.tool_events(self.TRACKER)
        self.assertEqual([c["after_user_turn"] for c in calls], [0, 0, 1])
        self.assertIn("activate", self.h.ENGINE_TOOLS)
        self.assertNotIn("get_policy_status", self.h.ENGINE_TOOLS)

    def test_text_metric_skips_hedged_sentences(self):
        metric = {"pattern": r"\b(?:it is|you're) covered\b", "unless_before": r"\bwhether\b"}
        text = self.TRACKER["events"][-1]["text"]
        self.assertEqual(self.h.text_metric_hits(metric, text), ["You're covered"])
        self.assertEqual(self.h.text_metric_hits(metric["pattern"], text), ["it is covered", "You're covered"])

    def test_percentile_is_nearest_rank(self):
        self.assertEqual(self.h.percentile([1, 2, 3, 4], 50), 2)
        self.assertEqual(self.h.percentile(list(range(1, 21)), 95), 19)
        self.assertIsNone(self.h.percentile([], 50))

    def test_usage_attribution_and_unpriced_calls(self):
        rows = [
            {"kind": "pricing"},
            {"kind": "llm_call", "ok": True, "sender_id": "a", "sender_source": "turn_context",
             "prompt_tokens": 10, "completion_tokens": 5, "reasoning_tokens": 4, "response_cost_usd": 0.5,
             "latency_ms": 100},
            {"kind": "llm_call", "ok": True, "sender_id": "a", "sender_source": "structlog_context",
             "prompt_tokens": 3, "completion_tokens": 0, "response_cost_usd": 0.25},
            {"kind": "llm_call", "ok": True, "sender_id": "b", "prompt_tokens": 1, "completion_tokens": 1,
             "response_cost_usd": None},
        ]
        a = self.h.usage_for(rows, "a")
        self.assertEqual((a["llm_calls"], a["side_channel_calls"], a["empty_completions"]), (2, 1, 1))
        self.assertEqual(a["cost_usd"], 0.75)
        self.assertIsNone(self.h.usage_for(rows, "b")["cost_usd"])

    def test_log_events_are_joined_on_conversation_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "server.log"
            log.write_text(
                'x WARNING m - {"event": "guard", "sender_id": "a", "level": "warning"}\n'
                'x WARNING m - {"event": "guard", "conversation_id": "b"}\n'
                "not json\n"
            )
            counts = self.h.log_events_for(log, "a", ["guard"])
            self.assertEqual(len(counts["guard"]), 1)

    def test_provider_errors_are_not_agent_failures(self):
        ok = [{"passed": True}]
        self.assertEqual(self.h.classify(None, ok, {"failed_calls": 0}), "pass")
        self.assertEqual(self.h.classify(None, [{"passed": False}], {"failed_calls": 0}), "fail")
        self.assertEqual(self.h.classify(None, [{"passed": False}], {"failed_calls": 3}), "provider_error")

    def test_variant_edits_files_for_the_run_and_restores_them(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            (project / "integrations.yml").write_text("model: x\n")
            spec = {"variants": {"low": {"edits": [
                {"file": "integrations.yml", "find": "model: x\n", "replace": "model: x\neffort: low\n"}]}}}
            variant = self.h.ProjectVariant(project, spec, "low")
            info = variant.__enter__()
            self.assertEqual(info["name"], "low")
            self.assertIn("effort: low", (project / "integrations.yml").read_text())
            variant.__exit__()
            self.assertEqual((project / "integrations.yml").read_text(), "model: x\n")
            bad = {"variants": {"low": {"edits": [{"file": "integrations.yml", "find": "nope", "replace": ""}]}}}
            with self.assertRaises(ValueError):
                self.h.ProjectVariant(project, bad, "low").__enter__()
            self.assertIsNone(self.h.ProjectVariant(project, spec, None).__enter__())

    def test_ledger_total_accumulates(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.h.ledger_append(project, {"run": "1", "cost_usd": 0.1})
            self.h.ledger_append(project, {"run": "2", "cost_usd": 0.2})
            self.assertAlmostEqual(self.h.ledger_total(project), 0.3)



class FakeBrowserAudioServer:
    """A stand-in for Rasa's browser_audio channel, built on its wire protocol.

    Handshake first, then JSON text frames. A caller turn ends after 200 ms of
    silence following speech, or on a `{"text"}` frame. The bot then answers
    with a start marker, audio, and an end marker carrying `latency`, and the
    fake tracker gains user, bot and bot_turn_ended events. Acknowledged
    markers are recorded.
    """

    RATE = 16000

    def __init__(self, reply_delay_s: float = 0.1, heard: str = "card ending four four one seven") -> None:
        import socket as _socket
        import threading as _threading

        self.reply_delay_s = reply_delay_s
        self.heard = heard
        self.events: list[dict] = []
        self.sent_markers: list[str] = []
        self.acked: list[str] = []
        self.sender_id = None
        self.frames_in = 0
        self.lock = _threading.Lock()
        self.listener = _socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.port = self.listener.getsockname()[1]
        self.thread = _threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def tracker(self, sender_id):
        with self.lock:
            return {"sender_id": sender_id, "events": [dict(e) for e in self.events]}

    def _send(self, obj):
        from voice_driver import OP_TEXT, encode_frame

        self.conn.sendall(encode_frame(OP_TEXT, json.dumps(obj).encode(), mask=False))

    def _marker(self, latency=None):
        import uuid

        marker = uuid.uuid4().hex
        self.sent_markers.append(marker)
        self._send({"marker": marker, **({"latency": latency} if latency else {})})

    def _speak(self, seconds):
        import base64 as b64
        import struct as st

        self._marker()
        n = int(self.RATE * seconds)
        tone = st.pack("<%dh" % n, *([1200, -1200] * (n // 2)))
        for i in range(0, len(tone), 4096):
            self._send({"audio": b64.b64encode(tone[i:i + 4096]).decode()})
        self._marker({"rasa_processing_latency_ms": 90.0, "tts_first_byte_latency_ms": 40.0,
                      "tts_complete_latency_ms": 60.0})

    def _reply(self, heard):
        import time as _time

        with self.lock:
            self.events.append({"event": "user", "text": heard})
        _time.sleep(self.reply_delay_s)
        self._speak(0.3)
        with self.lock:
            self.events.append({"event": "bot", "text": "Do you mean the card ending 4 4 1 7?"})
            self.events.append({"event": "bot_turn_ended", "metadata": {"latency_breakdown": {
                "user_perceived_latency_ms": 150.0,
                "first_agent_response": {"llm_time_to_first_token_ms": 80.0}}}})

    def _serve(self):
        import base64 as b64
        from voice_driver import OP_CLOSE, OP_TEXT, accept_key, read_frame

        self.conn, _ = self.listener.accept()
        request = b""
        while b"\r\n\r\n" not in request:
            request += self.conn.recv(4096)
        headers = dict(
            line.split(": ", 1) for line in request.decode().split("\r\n")[1:] if ": " in line
        )
        self.sender_id = headers.get("X-Rasa-Sender-Id")
        self.conn.sendall(
            ("HTTP/1.1 101 Switching Protocols\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
             f"Sec-WebSocket-Accept: {accept_key(headers['Sec-WebSocket-Key'])}\r\n\r\n").encode()
        )
        self._send({"type": "handshake", "sample_rate": self.RATE})
        self._speak(0.2)  # greeting
        speaking, silent = False, 0
        try:
            while True:
                _, opcode, payload = read_frame(self.conn)
                if opcode == OP_CLOSE:
                    break
                if opcode != OP_TEXT:
                    continue
                msg = json.loads(payload)
                if "marker" in msg:
                    self.acked.append(msg["marker"])
                elif "text" in msg:
                    self._reply(msg["text"])
                elif "audio" in msg:
                    self.frames_in += 1
                    if any(b64.b64decode(msg["audio"])):
                        speaking, silent = True, 0
                    elif speaking:
                        silent += 1
                        if silent >= 10:
                            speaking = False
                            self._reply(self.heard)
        except Exception:
            pass
        finally:
            self.conn.close()
            self.listener.close()


class TestBrowserAudioDriver(unittest.TestCase):
    """The voice driver against a fake browser_audio server. No Rasa, no vendor."""

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(_SCRIPTS / "case_builds"))
        import voice_driver
        import harness

        cls.v = voice_driver
        cls.h = harness

    def call(self, server, **kwargs):
        call = self.v.BrowserAudioCall(
            f"ws://127.0.0.1:{server.port}/webhooks/browser_audio/websocket", "conv-1",
            fetch_tracker=kwargs.pop("fetch_tracker", server.tracker), quiet_window_s=0.4, settle_s=0.2,
            turn_timeout_s=10, **kwargs,
        )
        call.open(greeting_timeout_s=5)
        return call

    @staticmethod
    def utterance(rate=16000):
        import struct as st

        silence = b"\x00\x00" * int(rate * 0.3)
        n = int(rate * 0.5)
        return silence + st.pack("<%dh" % n, *([3000, -3000] * (n // 2))) + silence

    def test_framing_round_trips_all_length_encodings(self):
        import socket as _socket

        a, b = _socket.socketpair()
        try:
            for size in (0, 125, 126, 70000):
                payload = bytes(range(256)) * (size // 256) + bytes(size % 256)
                import threading as _threading

                frame = self.v.encode_frame(self.v.OP_TEXT, payload, mask=True)
                sender = _threading.Thread(target=a.sendall, args=(frame,))
                sender.start()
                fin, opcode, got = self.v.read_frame(b)
                sender.join()
                self.assertEqual((fin, opcode, got), (True, self.v.OP_TEXT, payload))
        finally:
            a.close()
            b.close()

    def test_text_dry_run_measures_latency_and_reads_the_tracker(self):
        server = FakeBrowserAudioServer(reply_delay_s=0.15)
        call = self.call(server)
        result = call.say(text="block the card ending four four one seven", think_s=0)
        stats = call.close()
        self.assertEqual(server.sender_id, "conv-1")
        self.assertEqual(result["voice"]["ended_by"], "tracker")
        self.assertEqual(result["voice"]["heard"], ["block the card ending four four one seven"])
        self.assertGreaterEqual(result["latency_ms"], 140)
        self.assertLess(result["latency_ms"], 2000)
        self.assertEqual(result["voice"]["end_markers"][0]["rasa_processing_latency_ms"], 90.0)
        self.assertEqual(result["voice"]["latency_breakdown"][0]["user_perceived_latency_ms"], 150.0)
        self.assertEqual(result["bot_messages"][0]["text"], "Do you mean the card ending 4 4 1 7?")
        self.assertGreater(stats["audio_seconds_sent"], 0)  # silence streams even in dry-run

    def test_spoken_turn_times_end_of_speech_and_acks_every_marker(self):
        server = FakeBrowserAudioServer(reply_delay_s=0.1)
        call = self.call(server)
        result = call.say(pcm=self.utterance(), think_s=0)
        import time as _time

        _time.sleep(0.3)
        call.close()
        voice = result["voice"]
        self.assertEqual(voice["mode"], "audio")
        self.assertAlmostEqual(voice["speech_s"], 0.5, delta=0.02)
        # Server endpointing (10 silent 20 ms frames) plus its reply delay.
        self.assertGreaterEqual(result["latency_ms"], 250)
        self.assertLess(result["latency_ms"], 2500)
        self.assertEqual(voice["heard"], ["card ending four four one seven"])
        self.assertEqual(sorted(server.acked), sorted(server.sent_markers))
        self.assertEqual(voice["markers_pending"], 0)

    def test_quiet_window_ends_the_turn_without_a_tracker(self):
        server = FakeBrowserAudioServer()
        call = self.call(server, fetch_tracker=None)
        result = call.say(text="yes", think_s=0)
        call.close()
        self.assertEqual(result["voice"]["ended_by"], "quiet_window")
        self.assertIsNotNone(result["latency_ms"])

    def test_marker_on_an_empty_queue_waits_like_a_browser(self):
        sent = []
        speaker = self.v.Speaker(16000, sent.append)
        speaker.add_marker("late")
        import threading as _threading
        import time as _time

        _threading.Thread(target=speaker.run, daemon=True).start()
        _time.sleep(0.1)
        self.assertEqual(sent, [])
        speaker.enqueue(b"\x01\x00" * 160)
        _time.sleep(0.1)
        self.assertEqual(sent, ['{"marker": "late"}'])
        speaker.stop.set()

    def test_digit_and_name_checks(self):
        tokens = [{"token": "4417"}, {"token": "1986"}, {"token": "14"}, {"token": "Okafor", "kind": "name"}]
        spoken = self.v.check_tokens("Nadia Okafor, March fourteenth, nineteen eighty-six, ending four four one seven",
                                     tokens)
        self.assertEqual([t["normalised"] for t in spoken], [True, True, True, True])
        self.assertEqual([t["exact"] for t in spoken], [False, False, False, True])
        wrong = self.v.check_tokens("Nadia Okafur, ending 4 4 1 8", tokens)
        self.assertEqual([t["normalised"] for t in wrong], [False, False, False, False])
        self.assertEqual(self.v.number_runs("fifty five oh two"), [["55", "0", "2"]])

    def test_word_error_rate_ignores_number_spelling(self):
        self.assertEqual(self.v.word_error_rate("born nineteen eighty-six", "born 1986"), 0.0)
        self.assertAlmostEqual(self.v.word_error_rate("ending four four one seven", "ending 4 4 1 8"), 0.2)

    def test_speech_cost_and_voice_report(self):
        pricing = {"stt": {"usd_per_minute": 0.0065}, "tts": {"usd_per_1k_characters": 0.03}}
        cost = self.h.speech_cost(pricing, 120, 2000)
        self.assertEqual((cost["stt_usd"], cost["tts_usd"], cost["cost_usd"]), (0.013, 0.06, 0.073))
        self.assertIsNone(self.h.speech_cost({"stt": {"usd_per_minute": 0.0065}}, 60, 10)["cost_usd"])
        conv = {"turns": [{"user": "ending four four one seven", "asr_tokens": [{"token": "4417"}]}]}
        turns = [{"user": "ending four four one seven", "extra": {"mode": "audio", "heard": ["ending 4417"], "eos_to_first_audible_ms": 800.0,
                            "end_markers": [{"rasa_processing_latency_ms": 500.0}],
                            "latency_breakdown": [{"user_perceived_latency_ms": 700.0}], "ended_by": "tracker"}}]
        tracker = {"events": [{"event": "bot", "text": "x" * 100}]}
        report = self.h.voice_report({"speech_pricing": pricing}, conv, turns, tracker,
                                     {"audio_seconds_sent": 60, "mode": "audio"})
        self.assertEqual(report["tts_characters"], 100)
        self.assertEqual(report["asr"][0]["tokens"][0]["normalised"], True)
        self.assertEqual(report["asr"][0]["wer"], 0.0)
        agg = self.h.aggregate_voice([{"voice": report, "turns": turns}])
        self.assertEqual(agg["eos_to_first_audible_ms"]["p50"], 800.0)
        self.assertEqual(agg["asr"]["tokens"]["digits"], {"checked": 1, "exact": 1, "normalised": 1})
        self.assertEqual(agg["latency_breakdown_first"]["user_perceived_latency_ms"]["p50"], 700.0)
        changed = self.h.voice_report({}, conv, [dict(turns[0], user="an older script line")], tracker, {})
        self.assertEqual(changed["asr"], [])

    def test_repeated_latency_markers_collapse(self):
        a = {"rasa_processing_latency_ms": 900.0, "tts_first_byte_latency_ms": 500.0, "tts_complete_latency_ms": 1700.0}
        b = dict(a, tts_first_byte_latency_ms=200.0)
        got = self.v.dedupe_latency_markers([dict(a, at_ms=1), dict(a, at_ms=2), dict(b, at_ms=3)])
        self.assertEqual([m["at_ms"] for m in got], [1, 3])

    def test_card_endings_are_normalised_like_digits(self):
        got = self.v.check_tokens("ending four four one seven", [{"token": "4417", "kind": "card_ending"}])
        self.assertEqual((got[0]["exact"], got[0]["normalised"]), (False, True))

if __name__ == "__main__":
    # A suite that collects nothing exits 0 and prints nothing, which every
    # caller reads as a pass. That is not hypothetical: an edit once removed
    # this block, and `make validate` reported success while running no tests
    # at all. Assert the suite actually ran.
    _result = unittest.main(verbosity=2, exit=False).result
    if _result.testsRun == 0:
        print("no tests ran — the suite is not wired up", file=sys.stderr)
        raise SystemExit(1)
    raise SystemExit(0 if _result.wasSuccessful() else 1)
