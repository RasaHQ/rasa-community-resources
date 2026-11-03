"""The per-resource Codespaces configurations are generated, complete and consistent."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate_codespaces as g  # noqa: E402
from rasa_projects import REPO_ROOT, discover_projects  # noqa: E402


class GeneratedFilesTests(unittest.TestCase):
    def test_nothing_is_missing_or_stale(self):
        stale = [path for path, content in g.plan()
                 if not path.is_file() or path.read_text(encoding="utf-8") != content]
        self.assertEqual(stale, [], "run python3 scripts/generate_codespaces.py")

    def test_every_catalog_project_has_a_configuration_and_one_button(self):
        for project in discover_projects("catalog"):
            config = REPO_ROOT / ".devcontainer" / g.slug(project.rel) / "devcontainer.json"
            self.assertTrue(config.is_file(), project.rel)
            readme = (project.path / "README.md").read_text(encoding="utf-8")
            self.assertEqual(readme.count("Open in GitHub Codespaces"), 1, project.rel)
            self.assertIn(g.slug(project.rel) + "/devcontainer.json", readme)

    def test_manual_resources_are_covered(self):
        for item in g.MANUAL:
            self.assertTrue((REPO_ROOT / ".devcontainer" / g.slug(item["path"]) / "devcontainer.json").is_file())
            self.assertIn(g.START, (REPO_ROOT / item["path"] / "README.md").read_text(encoding="utf-8"))

    def test_configurations_share_one_image_and_declare_only_known_secrets(self):
        for entry in [g.manifest(p) for p in discover_projects("catalog")] + [g.manual_manifest(m) for m in g.MANUAL]:
            body = json.loads(g.config(entry))
            self.assertEqual(body["build"]["dockerfile"], "../resource-base/Dockerfile")
            self.assertIn("RASA_LICENSE", body["secrets"])
            self.assertLessEqual(set(body["secrets"]), set(g.KNOWN_SECRETS))
            self.assertTrue(body["workspaceFolder"].endswith("/" + entry["path"]))
            self.assertIn("ready.sh", body["postCreateCommand"])

    def test_sshd_feature_is_pinned_to_an_exact_version(self):
        for project in discover_projects("catalog"):
            body = json.loads((REPO_ROOT / ".devcontainer" / g.slug(project.rel) / "devcontainer.json").read_text())
            sshd = [name for name in body["features"] if "/sshd:" in name]
            self.assertEqual(sshd, [g.SSHD_FEATURE], project.rel)
            self.assertRegex(sshd[0], r":\d+\.\d+\.\d+$")
            self.assertEqual(body["features"][sshd[0]], {})

    def test_readme_discloses_what_the_ssh_feature_changes(self):
        text = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("PermitRootLogin yes", "port 2222", "gh codespace ssh", "PAM", "has not verified who or what can reach"):
            self.assertIn(phrase, text)
        self.assertNotIn("reaching it needs", text)

    def test_license_alias_comes_from_remote_env_for_resources_that_read_the_older_name(self):
        aliased = [g.manifest(p)["path"] for p in discover_projects("catalog") if g.manifest(p)["alias_license"]]
        self.assertEqual(len(aliased), 5)
        for path in discover_projects("catalog"):
            body = json.loads((REPO_ROOT / ".devcontainer" / g.slug(path.rel) / "devcontainer.json").read_text())
            if path.rel in aliased:
                self.assertEqual(body["remoteEnv"], {g.LICENSE_ALIAS: "${containerEnv:RASA_LICENSE}"}, path.rel)
                self.assertNotIn(g.LICENSE_ALIAS, body["secrets"])
            else:
                self.assertNotIn("remoteEnv", body, path.rel)
            self.assertNotIn("alias-license", body["onCreateCommand"])

    def test_installer_does_not_edit_shell_startup_files(self):
        self.assertNotIn("bashrc", (REPO_ROOT / ".devcontainer/resource-base/install.sh").read_text())


class PortTests(unittest.TestCase):
    EXPECTED = {
        "tutorials/frameworks-with-rasa/agno-mantle": [5020],
        "tutorials/frameworks-with-rasa/pipecat-mantle": [5020],
        "tutorials/frameworks-with-rasa/crewai-mantle": [5019],
        "tutorials/frameworks-with-rasa/langchain-mantle": [5017],
        "tutorials/frameworks-with-rasa/strands-mantle": [5018],
        "tutorials/jev-with-rasa/mantle": [5030],
        "tutorials/rasa-hubspot-crm-tutorial": [5005, 8787, 8931],
        "tutorials/voice-agent-three-frameworks/rasa": [5005, 8765],
        "examples/mantle-voice-agent": [5005],
    }

    def forwarded(self, rel):
        return json.loads((REPO_ROOT / ".devcontainer" / g.slug(rel) / "devcontainer.json").read_text())["forwardPorts"]

    def test_known_resources_forward_the_ports_their_makefiles_use(self):
        for rel, ports in self.EXPECTED.items():
            self.assertEqual(self.forwarded(rel), ports, rel)

    def test_every_resource_forwards_the_ports_derived_from_its_own_makefile(self):
        for project in discover_projects("catalog"):
            primary, forward = g.ports(project.path)
            self.assertEqual(self.forwarded(project.rel), forward, project.rel)
            self.assertIn(primary, forward, project.rel)
            readme = (project.path / "README.md").read_text(encoding="utf-8")
            if "starts on port" in readme:
                self.assertIn(f"port {primary}.", readme.split(g.END)[0], project.rel)

    def test_first_command_trains_before_it_inspects_or_runs(self):
        for project in discover_projects("catalog"):
            entry = g.manifest(project)
            if "train" in g.make_targets(project.path) and entry["first"] and project.rel not in g.FIRST:
                self.assertTrue(entry["first"].startswith("make train && make "), project.rel)


class EnvFileTests(unittest.TestCase):
    SCRIPT = REPO_ROOT / ".devcontainer/resource-base/make-env.sh"

    def run_script(self, directory, **env):
        environment = {"PATH": "/usr/bin:/bin", "HOME": directory}
        environment.update(env)
        return subprocess.run(["/bin/bash", str(self.SCRIPT), directory], env=environment, capture_output=True, text=True)

    def test_env_is_filled_from_present_secrets_only_and_never_printed(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text(
                "# note\nRASA_LICENSE=\nOPENAI_API_KEY=\nDEEPGRAM_API_KEY=\nLOG_LEVEL=INFO\n", encoding="utf-8")
            result = self.run_script(directory, RASA_LICENSE="license-sentinel", OPENAI_API_KEY="model-sentinel")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("sentinel", result.stdout + result.stderr)
            env = (Path(directory) / ".env").read_text(encoding="utf-8").splitlines()
            self.assertEqual(env, ["# note", "RASA_LICENSE=license-sentinel", "OPENAI_API_KEY=model-sentinel", "LOG_LEVEL=INFO"])
            self.assertEqual(stat.S_IMODE((Path(directory) / ".env").stat().st_mode), 0o600)

    def test_mode_is_600_even_when_the_umask_is_open_or_a_default_acl_would_override_it(self):
        # In a Codespace the workspace directory may carry a default ACL that wins over the umask. Model that by
        # running a copy of the script without its own `umask 077` line under an open umask: only the explicit chmod
        # can leave the file private.
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            copy = Path(directory) / "make-env-no-umask.sh"
            copy.write_text(self.SCRIPT.read_text().replace("umask 077\n", ""), encoding="utf-8")
            self.assertNotIn("umask 077", copy.read_text())
            environment = {"PATH": "/usr/bin:/bin", "HOME": directory, "OPENAI_API_KEY": "model-sentinel"}
            subprocess.run(["/bin/bash", "-c", f'umask 000; bash "{copy}" "{directory}"'], env=environment,
                           capture_output=True, text=True)
            self.assertEqual(stat.S_IMODE((Path(directory) / ".env").stat().st_mode), 0o600)

    def test_license_alias_is_filled_from_the_saved_license(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text("RASA_PRO_LICENSE=\n", encoding="utf-8")
            self.run_script(directory, RASA_LICENSE="license-sentinel")
            self.assertEqual((Path(directory) / ".env").read_text(encoding="utf-8"), "RASA_PRO_LICENSE=license-sentinel\n")

    def test_existing_env_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
            (Path(directory) / ".env").write_text("mine\n", encoding="utf-8")
            self.run_script(directory, OPENAI_API_KEY="model-sentinel")
            self.assertEqual((Path(directory) / ".env").read_text(encoding="utf-8"), "mine\n")


class ReadyTests(unittest.TestCase):
    SCRIPT = REPO_ROOT / ".devcontainer/resource-base/ready.sh"
    PROJECT = "examples/mantle-text-banking-transfer-gpt"

    def ready(self, **env):
        environment = {"PATH": "/usr/bin:/bin:" + os.path.dirname(sys.executable), "HOME": str(REPO_ROOT)}
        environment.update(env)
        return subprocess.run(["/bin/bash", str(self.SCRIPT), self.PROJECT, "true"], cwd=REPO_ROOT, env=environment,
                              capture_output=True, text=True).stdout

    def test_not_ready_names_missing_required_secrets(self):
        out = self.ready()
        self.assertIn("NOT READY", out)
        self.assertIn("RASA_LICENSE", out)

    def test_a_resource_whose_first_command_needs_nothing_is_ready_without_secrets(self):
        environment = {"PATH": "/usr/bin:/bin:" + os.path.dirname(sys.executable), "HOME": str(REPO_ROOT)}
        out = subprocess.run(["/bin/bash", str(self.SCRIPT), "tutorials/rasa-ai-team-casebook", "true"], cwd=REPO_ROOT,
                             env=environment, capture_output=True, text=True).stdout
        self.assertTrue(out.startswith("\nREADY"), out)

    def test_ready_when_required_secrets_are_set_or_ci_skips_them(self):
        required = json.loads((REPO_ROOT / ".devcontainer" / g.slug(self.PROJECT) / "devcontainer.json").read_text())["secrets"]
        names = [name for name, item in required.items() if item["description"].startswith("Required.")]
        self.assertTrue(self.ready(**{name: "x" for name in names}).startswith("\nREADY"))
        self.assertTrue(self.ready(READY_SKIP_SECRETS="1").startswith("\nREADY"))


class FirstUseHonestyTests(unittest.TestCase):
    def test_a_first_command_that_needs_nothing_does_not_demand_secrets(self):
        rel = "tutorials/rasa-ai-team-casebook"
        body = json.loads((REPO_ROOT / ".devcontainer" / g.slug(rel) / "devcontainer.json").read_text())
        self.assertTrue(all(item["description"].startswith("Optional.") for item in body["secrets"].values()))
        readme = (REPO_ROOT / rel / "README.md").read_text(encoding="utf-8").split(g.END)[0]
        self.assertIn("nothing for the first command", readme)
        self.assertNotIn("required `RASA_LICENSE`", readme)

    def test_resources_that_embed_references_say_training_is_a_billed_call(self):
        marked = 0
        for project in discover_projects("catalog"):
            readme = (project.path / "README.md").read_text(encoding="utf-8").split(g.END)[0]
            has = "reference documents with calls to your OpenAI account" in readme
            self.assertEqual(has, g.uses_references(project.path) and g.manifest(project)["first"] is not None
                             and project.rel not in g.FIRST, project.rel)
            marked += has
        self.assertGreaterEqual(marked, 5)

    def test_make_env_sets_the_mode_explicitly(self):
        self.assertIn("chmod 600 .env", (REPO_ROOT / ".devcontainer/resource-base/make-env.sh").read_text())


class ParsingTests(unittest.TestCase):
    def test_required_and_optional_come_from_the_section_headers(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / ".env.example").write_text(
                "# Required - license\nRASA_LICENSE=\n# Required - LLM\nOPENAI_API_KEY=\n"
                "# Optional - voice\nDEEPGRAM_API_KEY=\n",
                encoding="utf-8",
            )
            self.assertEqual(
                g.env_example_secrets(Path(directory)),
                {"RASA_LICENSE": True, "OPENAI_API_KEY": True, "DEEPGRAM_API_KEY": False},
            )

    def test_block_replacement_is_stable(self):
        block = g.START + "\nx\n" + g.END
        text = "# Title\n\nbody\n"
        once = g.with_block(text, block)
        self.assertEqual(g.with_block(once, block), once)
        self.assertEqual(once.count(g.START), 1)


if __name__ == "__main__":
    unittest.main()
