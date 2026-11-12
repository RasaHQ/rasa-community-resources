"""The per-resource Codespaces configurations are generated, complete and consistent."""
import json
import os
import re
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

    def test_every_frozen_heroes_project_has_a_config_button_and_own_pin_check(self):
        snapshots = discover_projects('snapshots')
        self.assertGreaterEqual(len(snapshots), 5)
        listed = json.loads(subprocess.check_output(
            [sys.executable, str(REPO_ROOT / 'scripts/generate_codespaces.py'), '--list-json'], text=True))
        for project in snapshots:
            with self.subTest(project=project.rel):
                path = REPO_ROOT / '.devcontainer' / g.slug(project.rel) / 'devcontainer.json'
                self.assertTrue(path.is_file())
                body = json.loads(path.read_text())
                self.assertIn('--use-project-pin', body['postCreateCommand'])
                self.assertIn('--skip-sync', body['postCreateCommand'])
                self.assertEqual(body['workspaceFolder'].split('/${localWorkspaceFolderBasename}/')[1], project.rel)
                self.assertIn({'path': project.rel, 'slug': g.slug(project.rel)}, listed)
                readme = (project.path / 'README.md').read_text()
                self.assertEqual(readme.count(g.START), 1)
                self.assertIn('ref=main&devcontainer_path=.devcontainer/' + g.slug(project.rel), readme)
                self.assertIn('its own locked Rasa version', readme)

    def test_snapshot_ready_command_reaches_checker_with_own_pin_and_no_sync(self):
        project = discover_projects('snapshots')[0]
        command = json.loads(g.config(g.manifest(project)))['postCreateCommand']
        with tempfile.TemporaryDirectory() as directory:
            probe = Path(directory) / 'python3'
            log = Path(directory) / 'arguments.txt'
            probe.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PROBE_LOG"\n')
            probe.chmod(0o755)
            environment = {'PATH': directory + ':/usr/bin:/bin', 'READY_SKIP_SECRETS': '1',
                           'PROBE_LOG': str(log), 'GIT_NO_LAZY_FETCH': '1'}
            result = subprocess.run(['/bin/bash', '-c', command], cwd=project.path,
                                    env=environment, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('READY:', result.stdout)
            self.assertEqual(log.read_text().splitlines(), [str(REPO_ROOT / 'scripts/check_project.py'),
                              project.rel, '--skip-sync', '--use-project-pin'])

    def test_heroes_provider_and_service_requirements_are_not_hidden(self):
        snapshots = {p.path.name: g.manifest(p) for p in discover_projects('snapshots')}
        terra = snapshots['ElarbiB-terra-energy']
        self.assertTrue(terra['secrets']['MISTRAL_API_KEY'])
        self.assertIn(8000, terra['ports'])
        self.assertIn('make backend', terra['before_first'])
        pilot = snapshots['traromal-devcopilot']
        pilot_config = json.loads(g.config(pilot))
        self.assertIn('DeepSeek', pilot_config['secrets']['DEEPSEEK_API_KEY']['description'])
        self.assertNotIn('OPENAI_API_KEY', pilot_config['secrets'])
        self.assertEqual(pilot_config['remoteEnv']['OPENAI_API_KEY'], '${containerEnv:DEEPSEEK_API_KEY}')
        self.assertIn('DeepSeek account key', g.readme_block(pilot, 4))
        self.assertIn('python -m scripts.mcp_demo_serve', pilot['before_first'])
        self.assertIn('python -m scripts.mcp_slack_serve', pilot['before_first'])
        self.assertFalse(pilot['secrets']['SLACK_BOT_TOKEN'])
        self.assertFalse(pilot['secrets']['SLACK_APP_TOKEN'])
        self.assertNotIn('Training uses your OpenAI key', g.readme_block(pilot, 4))
        coffee = snapshots['samrudh-coffee-shop']
        self.assertIn('LANGFUSE_PUBLIC_KEY', coffee['secrets'])
        self.assertIn('LANGFUSE_SECRET_KEY', coffee['secrets'])

    def test_civico_inspector_uses_its_default_port_not_the_separate_api_port(self):
        project = next(p for p in discover_projects('snapshots') if p.path.name == 'samakshmehra-civico')
        entry = g.manifest(project)
        self.assertEqual(entry['first'], 'make train && make inspect')
        self.assertIn(5005, entry['ports'])
        self.assertIn(5007, entry['ports'])
        self.assertNotIn('print-inspector-url.sh" 5007', entry['see'])

    def test_nourishher_declared_model_keys_are_available_to_its_codespace(self):
        project = next(p for p in discover_projects('snapshots') if p.path.name == 'malar-saravanan-nourishher-voice')
        entry = g.manifest(project)
        for name in ('RASA_LICENSE', 'OPENAI_API_KEY', 'GROQ_API_KEY', 'GEMINI_API_KEY', 'DEEPGRAM_API_KEY'):
            self.assertTrue(entry['secrets'].get(name), name)
        self.assertFalse(entry['secrets'].get('USDA_FDC_API_KEY', True))

    def test_nourishher_ready_invokes_its_existing_offline_suite_inside_the_project(self):
        project = next(p for p in discover_projects('snapshots') if p.path.name == 'malar-saravanan-nourishher-voice')
        command = json.loads(g.config(g.manifest(project)))['postCreateCommand']
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'python3').write_text('#!/bin/sh\nexit 0\n')
            (root / 'uv').write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PROBE_LOG"\npwd > "$PROBE_CWD"\n')
            for name in ('python3', 'uv'):
                (root / name).chmod(0o755)
            env = {'PATH': directory + ':/usr/bin:/bin', 'READY_SKIP_SECRETS': '1',
                   'PROBE_LOG': str(root / 'args'), 'PROBE_CWD': str(root / 'cwd'), 'GIT_NO_LAZY_FETCH': '1'}
            result = subprocess.run(['/bin/bash', '-c', command], cwd=project.path,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('READY:', result.stdout)
            self.assertEqual((root / 'cwd').read_text().strip(), str(project.path))
            self.assertEqual((root / 'args').read_text().splitlines(),
                             ['run', '--locked', '--no-sync', 'python', '-m', 'unittest', 'discover', '-s', 'tests', '-v'])

    def test_manual_resources_are_covered(self):
        for item in g.MANUAL:
            self.assertTrue((REPO_ROOT / ".devcontainer" / g.slug(item["path"]) / "devcontainer.json").is_file())
            self.assertIn(g.START, (REPO_ROOT / item["path"] / "README.md").read_text(encoding="utf-8"))

    def test_configurations_use_their_selected_image_and_declare_only_known_secrets(self):
        for entry in [g.manifest(p) for p in discover_projects("catalog")] + [g.manual_manifest(m) for m in g.MANUAL]:
            body = json.loads(g.config(entry))
            self.assertEqual(body["build"]["dockerfile"], "../resource-base/Dockerfile")
            self.assertEqual(len(set(body["secrets"]) & {"RASA_LICENSE", "RASA_PRO_LICENSE"}), 1)
            self.assertLessEqual(set(body["secrets"]), set(g.KNOWN_SECRETS))
            self.assertTrue(body["workspaceFolder"].endswith("/" + entry["path"]))
            self.assertIn("ready.sh", body["postCreateCommand"])

    def test_shared_configurations_do_not_install_python_through_a_feature(self):
        selected = {g.manifest(p)["path"] for p in discover_projects("catalog")}
        selected.update(m["path"] for m in g.MANUAL)
        for path in selected:
            body = json.loads((REPO_ROOT / ".devcontainer" / g.slug(path) / "devcontainer.json").read_text())
            self.assertFalse(any("/python:" in name for name in body["features"]), path)
            self.assertEqual(body["build"]["dockerfile"], "../resource-base/Dockerfile")
        dockerfile = (REPO_ROOT / ".devcontainer/resource-base/Dockerfile").read_text()
        self.assertRegex(dockerfile, r"FROM mcr\.microsoft\.com/devcontainers/python:1-3\.12-bookworm@sha256:[0-9a-f]{64}")
        self.assertIn("sys.version_info[:2] == (3, 12)", dockerfile)

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

    def test_resource_can_request_the_canonical_pro_license_without_a_second_secret(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "pyproject.toml").write_text(
                '[project]\nname = "banking-example"\n'
                '[tool.rasa-catalog]\nlicense-secret = "RASA_PRO_LICENSE"\n')
            (root / ".env.example").write_text(
                '# Required\nRASA_PRO_LICENSE=\nOPENAI_API_KEY=\nDEEPGRAM_API_KEY=\n')
            project = SimpleNamespace(path=root, pyproject=root / "pyproject.toml", rel="examples/bank")
            entry = g.manifest(project)
            body = json.loads(g.config(entry))
            self.assertEqual(set(body['secrets']), {'RASA_PRO_LICENSE', 'OPENAI_API_KEY', 'DEEPGRAM_API_KEY'})
            self.assertNotIn('remoteEnv', body)
            self.assertIn('`RASA_PRO_LICENSE`', g.readme_block(entry, 2))
            self.assertNotIn('`RASA_LICENSE`', g.readme_block(entry, 2))
            self.assertIn('configured by the operator as repository or organisation Codespaces secrets', g.readme_block(entry, 2))
            self.assertNotIn('personal Codespaces secrets', g.readme_block(entry, 2))
            (root / "pyproject.toml").write_text(
                '[project]\nname = "banking-example"\n'
                '[tool.rasa-catalog]\nlicense-secret = "ARBITRARY_TOKEN"\n')
            with self.assertRaisesRegex(ValueError, 'unsupported licence secret'):
                g.manifest(project)

    def test_a_failed_env_file_does_not_hide_a_failed_cd_in_the_manual_examples(self):
        for item in g.MANUAL:
            command = json.loads((REPO_ROOT / ".devcontainer" / g.slug(item["path"]) / "devcontainer.json").read_text())["onCreateCommand"]
            self.assertIn("&& { bash", command)
            self.assertIn("; } && ", command)

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


class InspectorCommandTests(unittest.TestCase):
    def test_nondefault_port_is_an_argument_not_part_of_the_script_name(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'pyproject.toml').write_text('[project]\nname = "port-fixture"\n')
            (root / 'Makefile').write_text('inspect:\n\tuv run rasa inspect --port 5037\n')
            entry = g.manifest(SimpleNamespace(path=root, pyproject=root / 'pyproject.toml', rel='examples/port-fixture'))
            command = re.search(r'`(bash [^`]+)`', entry['see']).group(1)
            probe = root / 'bash'
            log = root / 'arguments.txt'
            probe.write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PROBE_LOG"\n')
            probe.chmod(0o755)
            env = {'PATH': directory + ':/usr/bin:/bin', 'PROBE_LOG': str(log), 'GIT_NO_LAZY_FETCH': '1'}
            result = subprocess.run(['/bin/bash', '-c', command], cwd=REPO_ROOT,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().splitlines(),
                             [str(REPO_ROOT / '.devcontainer/resource-base/print-inspector-url.sh'), '5037'])


class FrozenRuntimeTests(unittest.TestCase):
    def execute_probes(self, expected, available_engine, actual=None):
        import contextlib
        import io
        import types
        from unittest.mock import patch
        from check_project import runtime_probes
        version, validate = runtime_probes(expected)
        called = []
        package = types.ModuleType('rasa')
        package.__path__ = []
        engine = types.ModuleType(available_engine)
        engine.__path__ = []
        validator = types.ModuleType(available_engine + '.validation')
        validator.validate_project = lambda path: called.append(path)
        modules = {'rasa': package, available_engine: engine, available_engine + '.validation': validator}
        with patch.dict(sys.modules, modules), patch('importlib.metadata.version', return_value=actual or expected), \
             patch('importlib.util.find_spec', side_effect=lambda name: object() if name == available_engine else None), \
             patch('logging.disable'), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            exec(version, {})
            exec(validate, {})
        return called

    def test_frozen_and_current_pins_use_their_own_engine_validation(self):
        for version, engine in [('3.19.0.dev5', 'rasa.calm_v2'), ('3.20.0.dev0', 'rasa.calm_v2'),
                                ('3.20.0.dev1', 'rasa.mantle'), ('3.21.0.dev5', 'rasa.mantle')]:
            with self.subTest(version=version):
                self.assertEqual(self.execute_probes(version, engine), [Path('.')])

    def test_newer_pin_does_not_accept_only_the_legacy_namespace(self):
        with self.assertRaises(SystemExit) as error:
            self.execute_probes('3.22.0.dev3', 'rasa.calm_v2')
        self.assertEqual(error.exception.code, 3)

    def test_wrong_installed_version_still_fails(self):
        with self.assertRaises(SystemExit) as error:
            self.execute_probes('3.19.0.dev5', 'rasa.calm_v2', actual='3.19.0.dev4')
        self.assertEqual(error.exception.code, 2)


class NoteVsSetupTests(unittest.TestCase):
    def test_setup_uses_its_lock_and_creates_a_private_local_env_template(self):
        script = REPO_ROOT / 'heroes/wave-01-mantle/projects/phlenfyl-notevs-agent/setup.sh'
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            script_copy = root / 'setup.sh'
            script_copy.write_bytes(script.read_bytes())
            (root / '.env.example').write_text('GROQ_API_KEY=\nRASA_LICENSE=\n')
            bin_dir = root / 'bin'
            bin_dir.mkdir()
            (bin_dir / 'python3.13').write_text('#!/bin/sh\nif [ "$1" = "--version" ]; then echo "Python 3.13 fixture"; else mkdir -p .venv/bin; : > .venv/bin/activate; fi\n')
            (bin_dir / 'pip').write_text('#!/bin/sh\nif [ "$1" = "install" ] && [ "$2" = "-r" ]; then test -f "$3" || exit 1; fi\n')
            (bin_dir / 'uv').write_text('#!/bin/sh\nprintf "%s\\n" "$@" > "$PROBE_LOG"\nprintf "%s\\n" "$UV_PROJECT_ENVIRONMENT" > "$PROBE_ENV"\n')
            for probe in bin_dir.iterdir():
                probe.chmod(0o755)
            env = {'PATH': str(bin_dir) + ':/usr/bin:/bin', 'PROBE_LOG': str(root / 'args'), 'PROBE_ENV': str(root / 'venv')}
            result = subprocess.run(['/bin/bash', str(script_copy)], env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertEqual((root / 'args').read_text().splitlines(), ['sync', '--locked', '--python', 'python3.13'])
            self.assertEqual((root / 'venv').read_text().strip(), str(root / '.venv'))
            self.assertEqual((root / '.env').read_bytes(), (root / '.env.example').read_bytes())
            self.assertEqual(stat.S_IMODE((root / '.env').stat().st_mode), 0o600)


class NoteVsWorkspaceBoundaryTests(unittest.TestCase):
    def test_production_tool_bodies_refuse_missing_scope_before_http(self):
        project = REPO_ROOT / 'heroes/wave-01-mantle/projects/phlenfyl-notevs-agent'
        result = subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'tests', '-v'],
                                cwd=project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('Ran 7 tests', result.stderr)
        entry = g.manifest(next(p for p in discover_projects('snapshots') if p.path == project))
        self.assertIn('--no-sync python -m unittest discover', entry['ready'])
        self.assertIn('do not expose or tunnel', entry['see'])


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

    def stubbed(self, directory, body):
        """A directory with a stub `chmod` first on the PATH, and the stub's log file."""
        bin_dir = Path(directory) / "bin"
        bin_dir.mkdir()
        stub = bin_dir / "chmod"
        stub.write_text("#!/bin/sh\n" + body)
        stub.chmod(0o755)
        return bin_dir

    def run_stubbed(self, directory, bin_dir, without_umask=False):
        """Run the script under an open umask. `without_umask` removes the script's own `umask 077`, modelling a
        directory whose default ACL overrides it, so that only an applied chmod can make the file private."""
        (Path(directory) / ".env.example").write_text("OPENAI_API_KEY=\n", encoding="utf-8")
        script = self.SCRIPT
        if without_umask:
            script = Path(directory) / "make-env-no-umask.sh"
            script.write_text(self.SCRIPT.read_text().replace("umask 077\n", ""), encoding="utf-8")
            self.assertNotIn("umask 077", script.read_text())
        environment = {"PATH": f"{bin_dir}:/usr/bin:/bin", "HOME": directory, "OPENAI_API_KEY": "model-sentinel"}
        return subprocess.run(["/bin/bash", "-c", f'umask 000; bash "{script}" "{directory}"'], env=environment,
                              capture_output=True, text=True)

    def test_the_file_is_still_empty_when_chmod_runs(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "size.log"
            bin_dir = self.stubbed(directory, f'wc -c < .env >> "{log}"\nexec /bin/chmod "$@"\n')
            result = self.run_stubbed(directory, bin_dir)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(log.read_text().split(), ["0"])
            self.assertEqual(stat.S_IMODE((Path(directory) / ".env").stat().st_mode), 0o600)

    def test_a_chmod_that_fails_writes_no_value_and_says_so_without_printing_one(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_stubbed(directory, self.stubbed(directory, "exit 1\n"))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("holds no secret", result.stderr)
            self.assertNotIn("sentinel", result.stdout + result.stderr)
            self.assertFalse((Path(directory) / ".env").exists())

    def test_a_chmod_that_silently_changes_nothing_is_caught_before_any_value_is_written(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_stubbed(directory, self.stubbed(directory, "exit 0\n"), without_umask=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("did not apply mode 600", result.stderr)
            self.assertFalse((Path(directory) / ".env").exists())

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

    def test_resources_that_embed_references_say_training_uses_the_openai_key(self):
        marked = 0
        for project in discover_projects("catalog"):
            readme = (project.path / "README.md").read_text(encoding="utf-8").split(g.END)[0]
            has = "uses your OpenAI key (a small embedding call)" in readme
            self.assertEqual(has, g.uses_references(project.path) and g.manifest(project)["first"] is not None
                             and project.rel not in g.FIRST, project.rel)
            marked += has
        self.assertGreaterEqual(marked, 5)

    def test_make_env_sets_and_verifies_the_mode_before_writing(self):
        text = (REPO_ROOT / ".devcontainer/resource-base/make-env.sh").read_text()
        self.assertLess(text.index("chmod 600 .env"), text.index("while IFS="))
        self.assertLess(text.index('mode_of .env'), text.index("while IFS="))


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
