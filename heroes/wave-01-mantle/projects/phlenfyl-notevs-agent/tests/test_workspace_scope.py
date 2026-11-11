"""Run shipped async tool bodies with a fake SDK result and HTTP transport.

AST extraction avoids installing the SDK for these boundary controls. This
suite does not establish SDK decorator, extension, notes or provider behaviour.
"""
import ast
import asyncio
import inspect
from pathlib import Path
from types import SimpleNamespace
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'tools' / 'notevs_tools.py'


class WorkspaceScopeTests(unittest.TestCase):
    def setUp(self):
        self.requests = []
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
                   'NOTEVS_CALL_URL': 'http://localhost:37492/call', 'NOTEVS_FOLDER_PATH': None}
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
        folder = '/desktop/notes/Project with spaces'
        self.ns['NOTEVS_FOLDER_PATH'] = folder
        args = {'query': 'fixture'}
        self.assertTrue(self.call('notevs_search_notes', args)['ok'])
        self.assertEqual(self.requests, [('http://localhost:37492/call',
                         {'tool': 'notevs_search_notes', 'args': {'query': 'fixture', 'folderPath': folder}})])
        self.assertEqual(args, {'query': 'fixture'})

    def test_caller_args_cannot_replace_the_configured_workspace(self):
        self.ns['NOTEVS_FOLDER_PATH'] = '/desktop/intended'
        self.call('notevs_delete_note', {'folderPath': '/desktop/other', 'id': 'fixture'})
        self.assertEqual(self.requests[0][1]['args']['folderPath'], '/desktop/intended')


if __name__ == '__main__':
    unittest.main()
