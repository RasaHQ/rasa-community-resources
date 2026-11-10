import asyncio,json,os,sys,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'shared'))
from bank_research.bridge import investigate


class WorkerBoundary(unittest.IsolatedAsyncioTestCase):
    async def test_worker_receives_only_selected_snapshot_and_model_credential(self):
        captured={}
        evidence={'transaction':{'amount':'49.00'}}
        class Process:
            returncode=0
            async def communicate(self,value):
                captured['stdin']=json.loads(value)
                return json.dumps({'status':'research_complete','evidence':evidence}).encode(),b''
        async def spawn(*args,**kwargs):
            captured['args']=args;captured['env']=kwargs['env'];return Process()
        with patch.dict(os.environ,{'BANK_RESEARCH_PYTHON':sys.executable,'OPENAI_API_KEY':'offline-placeholder','RIME_API_KEY':'must-not-transfer','RASA_PRO_LICENSE':'must-not-transfer'}),patch('asyncio.create_subprocess_exec',spawn):
            result=await investigate(evidence)
        self.assertEqual(result['status'],'research_complete')
        self.assertEqual(captured['stdin'],evidence)
        self.assertNotIn('RIME_API_KEY',captured['env']);self.assertNotIn('RASA_PRO_LICENSE',captured['env'])
        self.assertNotIn('PYTHONPATH',captured['env'])

    async def test_altered_worker_evidence_refused(self):
        class Process:
            returncode=0
            async def communicate(self,value):
                return b'{"status":"research_complete","evidence":{"transaction":{"amount":"0.00"}}}',b''
        async def spawn(*args,**kwargs):return Process()
        with patch.dict(os.environ,{'BANK_RESEARCH_PYTHON':sys.executable,'OPENAI_API_KEY':'offline-placeholder'}),patch('asyncio.create_subprocess_exec',spawn):
            result=await investigate({'transaction':{'amount':'49.00'}})
        self.assertEqual(result['error'],'research_invalid_evidence')

    async def test_missing_config_does_not_start_process(self):
        with patch.dict(os.environ,{},clear=True),patch('asyncio.create_subprocess_exec') as spawn:
            self.assertEqual(await investigate({}),{'error':'research_not_configured'})
            spawn.assert_not_called()

    async def test_timeout_kills_only_invocation_child(self):
        class Process:
            returncode=None
            killed=False
            async def communicate(self,value):raise asyncio.TimeoutError()
            def kill(self):self.killed=True
            async def wait(self):self.returncode=-9
        process=Process()
        async def spawn(*args,**kwargs):return process
        with patch.dict(os.environ,{'BANK_RESEARCH_PYTHON':sys.executable,'OPENAI_API_KEY':'offline-placeholder'}),patch('asyncio.create_subprocess_exec',spawn):
            result=await investigate({'transaction':{}})
        self.assertEqual(result['error'],'research_unavailable');self.assertTrue(process.killed)

if __name__=='__main__':unittest.main()
