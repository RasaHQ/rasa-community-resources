"""Clean setup and isolated-port regression checks.
sow: software-factories-masterclass-SOW-02
"""
from argparse import Namespace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch
import launcher

class LauncherTests(unittest.TestCase):
    def args(self, **changes):
        v=dict(host='127.0.0.1', viewer_access='', viewer_name='', allow_peer=[],
               entry_port=8960, inspector_port=5020, mcp_port=8961,
               builder_mode='SCRIPTED', worker_python='/absent/live-worker',
               env_file=None, evidence_root='/unused',
               expires_at=(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat())
        v.update(changes)
        return Namespace(**v)

    def test_invalid_or_repeated_ports_fail_before_binding(self):
        for changes in ({'entry_port':0},{'mcp_port':65536},{'mcp_port':8960}):
            with self.subTest(changes=changes),patch.object(launcher.socket,'socket') as bind:
                with self.assertRaisesRegex(ValueError,'distinct ports'):
                    launcher.run(self.args(**changes))
                bind.assert_not_called()

    def test_frontend_targets_selected_inspector(self):
        from server import frontend
        from starlette.testclient import TestClient
        with patch.dict(os.environ,{'FACTORY_ALLOWED_PEERS':'testclient','FACTORY_INSPECTOR_PORT':'5020','FACTORY_VIEWER_NAME':'127.0.0.1'},clear=True):
            r=TestClient(frontend('127.0.0.1')).get('/')
            self.assertEqual(r.status_code,200)
            self.assertIn('127.0.0.1:5020/webhooks/inspector/',r.text)
            self.assertIn('127.0.0.1%3A5020',r.text)
            self.assertNotIn(':5007',r.text)

if __name__=='__main__':unittest.main()

class MCPPortTests(unittest.TestCase):
    def test_configured_port_changes_only_factory_connection_and_preserves_token(self):
        from rasa.mantle.config.mcp import MCPServersSettings
        original=MCPServersSettings.to_connection_config
        try:
            with patch.object(MCPServersSettings,'to_connection_config',return_value={'url':'http://127.0.0.1:8948/mcp','token':'synthetic-token'}):
                launcher.install_mcp_port(8965)
                result=MCPServersSettings.to_connection_config(None,'factory')
                self.assertEqual(result,{'url':'http://127.0.0.1:8965/mcp','token':'synthetic-token'})
        finally:MCPServersSettings.to_connection_config=original
