"""Regression cases for example dependency boundaries, not runtime sandboxing."""
from pathlib import Path
import tempfile
import unittest

from datetime import date
from check_self_contained import inspect, exception_findings, KNOWN


class ExampleClosureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.files = []

    def put(self, relative, raw):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(raw)
        self.files.append(relative)
        return path

    def findings(self):
        return inspect(self.root, self.files)

    def test_normal_sdk_and_local_package_are_allowed(self):
        self.put('examples/a/pyproject.toml', '[project]\nname="a"\ndependencies=["rasa-pro==3.21.0.dev5", "mcp>=1"]\n[tool.uv.sources]\nhelper={path="local-helper"}\n')
        self.put('examples/a/app.py', 'import json\nfrom pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nvalue=(PROJECT/"data.json").read_text()\n')
        self.assertEqual(self.findings(), [])

    def test_sibling_pyproject_source_is_refused(self):
        self.put('examples/a/pyproject.toml', '[tool.uv.sources]\nshared={path="../b",editable=true}\n')
        self.assertTrue(self.findings())

    def test_lock_editable_directory_and_virtual_sources_are_checked(self):
        for key in ('editable', 'directory', 'virtual'):
            with self.subTest(key=key):
                self.files = []
                self.put('examples/a/uv.lock', '[[package]]\nname="x"\nsource={'+key+'="../../patterns/shared"}\n')
                self.assertTrue(self.findings())

    def test_file_uri_dependency_is_refused(self):
        self.put('examples/a/pyproject.toml', '[project]\ndependencies=["shared @ file:../b"]\n')
        self.assertTrue(self.findings())

    def test_removed_shared_distribution_cannot_return_from_registry(self):
        self.put('examples/a/pyproject.toml', '[project]\ndependencies=["banking-demo-shared>=1"]\n')
        self.assertTrue(self.findings())

    def test_zeo_imports_are_refused_under_aliases(self):
        self.put('examples/a/app.py', 'import zeocore as core\nfrom zeointegrations.client import Client as C\n')
        self.assertEqual(len(self.findings()), 2)

    def test_literal_dynamic_import_and_concatenation_are_refused(self):
        self.put('examples/a/app.py', 'from importlib import import_module as load\nload("zeo"+"core")\n')
        self.assertTrue(self.findings())

    def test_repository_namespace_import_is_not_a_package_escape(self):
        self.put('examples/a/app.py', 'from patterns.shared import tool\n')
        self.assertTrue(self.findings())

    def test_local_namespace_is_allowed(self):
        self.put('examples/a/scripts/helper.py', 'value=1\n')
        self.put('examples/a/app.py', 'from scripts.helper import value\n')
        self.assertEqual(self.findings(), [])

    def test_import_path_leaving_example_is_refused(self):
        self.put('examples/a/app.py', 'import sys\nfrom pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nsys.path.insert(0,str(PROJECT.parent/"b"))\n')
        self.assertTrue(self.findings())

    def test_local_test_import_path_is_allowed(self):
        self.put('examples/a/tests/check.py', 'import sys\nfrom pathlib import Path\nPROJECT=Path(__file__).resolve().parents[1]\nsys.path.insert(0,str(PROJECT))\n')
        self.assertEqual(self.findings(), [])

    def test_pathlib_alias_and_sys_path_alias_do_not_bypass(self):
        self.put('examples/a/app.py', 'from pathlib import Path as P\nfrom sys import path as search\nPROJECT=P(__file__).resolve().parent\nsearch.append(str(PROJECT.parent/"b"))\n')
        self.assertTrue(self.findings())

    def test_unresolved_search_path_does_not_silently_pass(self):
        self.put('examples/a/app.py', 'import sys\nsys.path.append(user_path)\n')
        self.assertTrue(self.findings())

    def test_parent_io_and_fstring_path_are_refused(self):
        self.put('examples/a/app.py', 'from pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nopen(f"{PROJECT}/../b/data.json")\n')
        self.assertTrue(self.findings())

    def test_negative_parent_index_is_checked(self):
        self.put('examples/a/app.py', 'from pathlib import Path\n(Path(__file__).parents[-1]/"data.json").read_text()\n')
        self.assertTrue(self.findings())

    def test_relative_import_leaving_example_is_refused(self):
        self.put('examples/a/app.py', 'from ..b import value\n')
        self.assertTrue(self.findings())

    def test_shell_parent_reference_is_refused(self):
        self.put('examples/a/Makefile', 'REPO=../..\nrun:\n\tpython $(REPO)/scripts/runner.py\n')
        self.assertTrue(self.findings())

    def test_subprocess_source_argument_is_checked(self):
        self.put('examples/a/app.py', 'import subprocess\nfrom pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nsubprocess.run(["python",str(PROJECT.parent/"b/run.py")])\n')
        self.assertTrue(self.findings())

    def test_data_string_is_not_mistaken_for_source_access(self):
        self.put('examples/a/test.py', 'malicious_input={"path":"../outside"}\nassert malicious_input["path"] == "../outside"\n')
        self.assertEqual(self.findings(), [])

    def test_symlink_cannot_hide_a_foreign_module(self):
        target = self.put('examples/b/app.py', 'value=1\n')
        path = self.root/'examples/a/leak.py'
        path.parent.mkdir(exist_ok=True)
        path.symlink_to(target)
        self.files.append('examples/a/leak.py')
        self.assertTrue(self.findings())

    def test_only_named_devcontainer_dockerfile_is_an_exception(self):
        self.put('examples/a/app.py', 'from pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nREPO=PROJECT.parent.parent\n(REPO/".devcontainer/resource-base/Dockerfile").read_text()\n')
        self.assertEqual(self.findings(), [])
        self.put('examples/a/app.py', 'from pathlib import Path\nPROJECT=Path(__file__).resolve().parent\nREPO=PROJECT.parent.parent\n(REPO/"scripts/helper.py").read_text()\n')
        self.assertTrue(self.findings())

    def test_parse_failure_is_a_finding_not_a_skipped_file(self):
        self.put('examples/a/broken.py', 'def broken(:\n')
        self.assertTrue(self.findings())


class RuntimeScopeTests(unittest.TestCase):
    setUp = ExampleClosureTests.setUp
    put = ExampleClosureTests.put
    findings = ExampleClosureTests.findings
    def test_central_parity_test_is_not_application_dependency(self):
        self.put('examples/a/tests/test_parity.py', 'from pathlib import Path\n(Path(__file__).parents[3]/"casebook/case.json").read_text()\n')
        self.assertEqual(self.findings(), [])

    def test_authoring_exclusion_cannot_hide_forbidden_import(self):
        self.put('examples/a/tests/test_parity.py', 'import zeocore\n')
        self.assertTrue(self.findings())

    def test_runtime_import_promotes_control_back_into_scope(self):
        self.put('examples/a/app.py', 'from controls import helper\n')
        self.put('examples/a/controls/helper.py', 'from pathlib import Path\n(Path(__file__).parents[3]/"casebook/case.json").read_text()\n')
        self.assertTrue(self.findings())

    def test_authoring_recipe_does_not_make_install_depend_on_repo(self):
        self.put('examples/a/Makefile', 'REPO=../..\nrun:\n\tuv run rasa run\nconversations:\n\tpython $(REPO)/scripts/runner.py\n')
        self.assertEqual(self.findings(), [])

    def test_runtime_prerequisite_cannot_hide_parent_recipe(self):
        self.put('examples/a/Makefile', 'ROOT=../..\nrun: helper\nhelper:\n\tpython $(ROOT)/scripts/runner.py\n')
        self.assertTrue(self.findings())

    def test_nested_manifest_source_is_relative_to_manifest(self):
        self.put('examples/a/worker/pyproject.toml', '[tool.uv.sources]\nhelper={path="../helper"}\n')
        self.assertEqual(self.findings(), [])
        self.put('examples/a/worker/pyproject.toml', '[tool.uv.sources]\nhelper={path="../../b"}\n')
        self.assertTrue(self.findings())

    def test_runtime_prompt_path_is_checked(self):
        self.put('examples/a/config.yml', 'prompt_file: ../../prompts/shared.txt\n')
        self.assertTrue(self.findings())

    def test_voice_exception_is_scoped_to_exact_path_and_example(self):
        self.put('examples/mantle-voice-routed-skills/pyproject.toml', '[tool.uv.sources]\nrouter={path="../../patterns/voice-vendor-router"}\n')
        rows = [{'example': 'mantle-voice-routed-skills', 'violation': 'patterns/voice-vendor-router'}]
        self.assertEqual(inspect(self.root, self.files, rows), [])
        self.put('examples/a/pyproject.toml', '[tool.uv.sources]\nrouter={path="../../patterns/voice-vendor-router"}\n')
        self.assertTrue(inspect(self.root, self.files, rows))

    def test_debt_cannot_waive_python_import(self):
        self.put('examples/mantle-factory-agent/app.py', 'import zeocore\n')
        rows = [{'example': 'mantle-factory-agent', 'violation': 'zeocore distribution'}]
        self.assertTrue(inspect(self.root, self.files, rows))

    def test_debt_only_shrinks_and_expires(self):
        rows = [{'example': key, 'violation': val[0], 'fix_by': val[1]} for key, val in KNOWN.items()]
        self.assertEqual(exception_findings(rows, today=date(2026,11,12)), [])
        self.assertEqual(exception_findings(rows[:-1], rows, date(2026,11,12)), [])
        self.assertTrue(exception_findings(rows, rows[:-1], date(2026,11,12)))
        self.assertTrue(exception_findings(rows, today=date(2026,11,16)))
        extended = [dict(rows[0], fix_by='2026-11-20')]
        self.assertTrue(exception_findings(extended, rows, date(2026,11,12)))


if __name__ == '__main__':
    unittest.main()
