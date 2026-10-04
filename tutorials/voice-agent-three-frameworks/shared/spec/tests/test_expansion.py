import tempfile
import unittest
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE))
import run_spec
from source_receipt import source_receipt

class Expansion(unittest.TestCase):
    def test_eight_versions_use_the_same_audit_protocol(self):
        self.assertEqual(set(run_spec.PRESETS), {'rasa','langgraph','strands','langchain','agno','crewai','pipecat','livekit'})
        for preset in run_spec.PRESETS.values():
            self.assertEqual(preset['ws_path'],'/webhooks/browser_audio/websocket')
            self.assertTrue((run_spec.TUTORIAL/preset['cwd']/'uv.lock').is_file())
    def test_receipt_changes_with_source_without_reading_secrets_or_environments(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);project=root/'agno';project.mkdir()
            (project/'agent.py').write_text('x = 1\n')
            (project/'.env').write_text('secret')
            (project/'.venv').mkdir();(project/'.venv'/'bad.py').write_text('do not hash')
            a=source_receipt(root,project,'agno')
            self.assertEqual(set(a['file_sha256']), {'agno/agent.py'})
            (project/'agent.py').write_text('x = 2\n')
            b=source_receipt(root,project,'agno');self.assertNotEqual(a['inputs_sha256'],b['inputs_sha256'])

    def test_startup_failure_is_retained_and_label_cannot_overwrite_it(self):
        from unittest import mock
        import json
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            private_output=root/'private-output'
            argv=['run_spec.py','agno','--results-root',str(private_output),'--label','failed-start','--only','normal-lisinopril']
            with mock.patch.object(run_spec,'TUTORIAL',root), mock.patch.object(sys,'argv',argv), \
                 mock.patch.object(run_spec.AgentProcess,'start',side_effect=RuntimeError('scripted startup failure')):
                self.assertEqual(run_spec.main(),1)
                result=json.loads((private_output/'agno/failed-start/results.json').read_text())
                self.assertFalse((root/'results').exists())
                self.assertEqual(result['status'],'startup_error')
                self.assertEqual(result['aggregate']['conversations_run'],0)
                ledger=json.loads((private_output/'agno/spend-ledger.json').read_text())
                self.assertEqual(ledger['runs'][0]['status'],'startup_error')
                with self.assertRaises(SystemExit) as error:run_spec.main()
                self.assertEqual(error.exception.code,2)
                self.assertEqual(len(json.loads((private_output/'agno/spend-ledger.json').read_text())['runs']),1)

    def test_meter_rejects_sdk_fallback_without_contacting_provider(self):
        import json
        import urllib.request
        import urllib.error
        from llm_meter import LLMMeter
        # Port 1 has no provider: a mismatch must be rejected locally before connecting.
        meter=LLMMeter({},upstream='http://127.0.0.1:1',model_id='pinned',reasoning_effort='low').start()
        try:
            for body in [{'model':'other','reasoning':{'effort':'low'}},
                         {'model':'pinned','reasoning':{'effort':'none'}},
                         {'model':'pinned'}]:
                request=urllib.request.Request(meter.base_url+'/responses',
                    data=json.dumps(body).encode(),headers={'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(request)
                self.assertEqual(error.exception.code,409)
                error.exception.close()
            self.assertEqual(len(meter.rows),3)
            self.assertTrue(all(r['upstream_called'] is False for r in meter.rows))
            self.assertEqual(meter.total_cost(),0)
        finally:meter.stop()
