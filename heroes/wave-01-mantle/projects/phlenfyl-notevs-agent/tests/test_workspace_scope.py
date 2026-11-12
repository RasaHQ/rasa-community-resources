"""Run shipped async tool bodies with a fake SDK result and HTTP transport.

AST extraction avoids installing the SDK for these boundary controls. This
suite does not establish SDK decorator, extension, notes or provider behaviour.
"""
import ast
import asyncio
import inspect
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tools' / 'notevs_tools.py'


class WorkspaceScopeTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.folder = Path(self.tmp.name).resolve() / 'Project with spaces'
        self.folder.mkdir()
        owner = self

        class Client:
            def __init__(self, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def post(self, url, json):
                owner.requests.append((url, json))
                return SimpleNamespace(status_code=200, json=lambda: {'result': {'ok': True}})

        tree = ast.parse(SOURCE.read_text())
        functions = [n for n in tree.body if isinstance(n, ast.AsyncFunctionDef)]
        self.tool_names = [node.name for node in functions if node.name != "_call"]
        for node in functions:
            node.decorator_list = []
        self.ns = {'ToolContext': object, 'ToolResult': SimpleNamespace,
                   'httpx': SimpleNamespace(AsyncClient=Client, HTTPError=OSError),
                   'Path': Path, 'NOTEVS_CALL_URL': 'http://localhost:37492/call', 'NOTEVS_FOLDER_PATH': None}
        exec(compile(ast.Module(body=functions, type_ignores=[]), str(SOURCE), 'exec'), self.ns)

    def call(self, name, args):
        return asyncio.run(self.ns['_call'](name, args)).llm_response

    def test_missing_or_blank_workspace_prevents_all_note_io(self):
        for scope in (None, '', '  ', '\t\n'):
            self.ns['NOTEVS_FOLDER_PATH'] = scope
            for tool in self.tool_names:
                with self.subTest(scope=scope, tool=tool):
                    function = self.ns[tool]
                    args = {key: 'fixture' for key, parameter in inspect.signature(function).parameters.items()
                            if parameter.default is inspect.Parameter.empty}
                    result = asyncio.run(function(**args)).llm_response
                    self.assertFalse(result['ok'])
                    self.assertEqual(result['error'], 'workspace_scope_required')
        self.assertEqual(self.requests, [])

    def test_configured_extension_host_workspace_is_forwarded_exactly(self):
        folder = str(self.folder)
        self.ns['NOTEVS_FOLDER_PATH'] = folder
        args = {'query': 'fixture'}
        self.assertTrue(self.call('notevs_search_notes', args)['ok'])
        self.assertEqual(self.requests, [('http://localhost:37492/call',
                         {'tool': 'notevs_search_notes', 'args': {'query': 'fixture', 'folderPath': folder}})])
        self.assertEqual(args, {'query': 'fixture'})

    def test_caller_args_cannot_replace_the_configured_workspace(self):
        self.ns['NOTEVS_FOLDER_PATH'] = str(self.folder)
        self.call('notevs_delete_note', {'folderPath': '/desktop/other', 'id': 'fixture'})
        self.assertEqual(self.requests[0][1]['args']['folderPath'], str(self.folder))

    def test_relative_missing_and_file_paths_are_refused_before_http(self):
        file_path = Path(self.tmp.name) / 'not-a-directory'
        file_path.write_text('fixture')
        for value in ('relative/workspace', str(self.folder / 'missing'), str(file_path)):
            with self.subTest(value=value):
                self.ns['NOTEVS_FOLDER_PATH'] = value
                result = self.call('notevs_list_notes', {})
                self.assertFalse(result['ok'])
                self.assertEqual(result['error'], 'workspace_scope_invalid')
        self.assertEqual(self.requests, [])

    def test_unresolvable_workspace_is_refused_before_http(self):
        self.ns['NOTEVS_FOLDER_PATH'] = str(self.folder)
        for error in (OSError('resolution failure'), RuntimeError('symlink loop'), ValueError('invalid path')):
            with self.subTest(error=type(error).__name__):
                with patch.object(Path, 'resolve', side_effect=error):
                    result = self.call('notevs_create_note', {'title': 'fixture'})
                self.assertFalse(result['ok'])
                self.assertEqual(result['error'], 'workspace_scope_invalid')
        self.assertEqual(self.requests, [])

    def test_existing_directory_alias_is_sent_as_canonical_path(self):
        alias = Path(self.tmp.name) / 'alias'
        try:
            alias.symlink_to(self.folder, target_is_directory=True)
        except OSError:
            self.skipTest('Directory symlinks unavailable on this host')
        self.ns['NOTEVS_FOLDER_PATH'] = str(alias)
        self.call('notevs_search_notes', {'query': 'fixture'})
        self.assertEqual(self.requests[0][1]['args']['folderPath'], str(self.folder))

    def test_env_template_does_not_override_an_injected_workspace_binding(self):
        shell = shutil.which('bash')
        if shell is None:
            self.skipTest('Bash is needed by start.sh and this template-load control')
        template = SOURCE.parents[1] / '.env.example'
        env = dict(os.environ, NOTEVS_FOLDER_PATH=str(self.folder),
                   NOTEVS_CALL_URL='http://127.0.0.1:37492/call')
        result = subprocess.run([shell, '-c',
            'source "$1"; printf "%s\\n%s\\n" "$NOTEVS_FOLDER_PATH" "$NOTEVS_CALL_URL"',
            'template-test', str(template)], env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.folder), 'http://127.0.0.1:37492/call'])


if __name__ == '__main__':
    unittest.main()
