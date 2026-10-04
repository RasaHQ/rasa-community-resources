"""Verify reverse-patch reconstruction and execute the native SDK countertest."""
from pathlib import Path
import asyncio
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
TUTORIAL=HERE.parents[1]
name=sys.argv[1]
project=TUTORIAL/name
sys.path[:0]=[str(project),str(project/'tests')]
os.environ['OPENAI_API_KEY']='offline-test'
os.environ['AGNO_TELEMETRY']='false'
os.environ['CREWAI_TELEMETRY_DISABLED']='true'
import agent as guarded
import test_agent
from cedar_clinic import refills
from cedar_clinic.audit import AUDIT

def load(path):
    spec=importlib.util.spec_from_file_location('countertest_agent',path)
    module=importlib.util.module_from_spec(spec)
    sys.modules[spec.name]=module;spec.loader.exec_module(module)
    return module

async def execute(module):
    refills.reset_services();AUDIT.clear()
    model=test_agent.Model() if name=='langchain' else test_agent.ScriptedModel([])
    args={'llm':model} if name in ('crewai','pipecat') else {'model':model}
    c=module.Conversation('countertest-'+name,**args)
    if name=='langchain':
        c._execute(test_agent.call('verify_patient',full_name='Maria Alvarez',date_of_birth='1968-03-14'))
        selected=c._execute(test_agent.call('select_medication',medication_name='lisinopril'))
    elif name=='agno':
        functions={f.name:f.entrypoint for f in c.tools}
        functions['verify_patient']('Maria Alvarez','1968-03-14')
        selected=functions['select_medication']('lisinopril')
    else:
        await c.execute('verify_patient',{'full_name':'Maria Alvarez','date_of_birth':'1968-03-14'})
        selected=json.loads(await c.execute('select_medication',{'medication_name':'lisinopril'}))
        while not c.queue.empty():c.queue.get_nowait()
    call=('send_refill_request',{'record_id':selected['record_id']})
    if name=='langchain':model.outputs=[[test_agent.call(call[0],**call[1])],'Awaiting team review.']
    elif name=='crewai':c.agent.llm._outputs=[call,'Awaiting team review.']
    else:model.outputs=[call,'Awaiting team review.']
    async def turn():return [s async for s in c.turn('Please send the request')]
    said=await asyncio.wait_for(turn(),8)
    effects=sum(e['result'].get('effects',0) for e in AUDIT.entries('countertest-'+name))
    result={'effects_before_caller_confirmation':effects,'readback':any(s.source=='confirmation' for s in said),
            'audit_entries':len(AUDIT.entries('countertest-'+name))}
    if hasattr(c,'close'):await c.close()
    return result

with tempfile.TemporaryDirectory() as temp:
    directory=Path(temp)
    for filename in ['agent.py','guard.py']:(directory/filename).write_bytes((project/filename).read_bytes())
    diff=(project/'guard.diff').read_bytes()
    subprocess.run(['patch','-R','-E','--fuzz=0','-p1'],input=diff,cwd=directory,check=True,capture_output=True)
    baseline=directory/'agent.py'
    compile(baseline.read_text(), str(baseline), 'exec')
    assert not (directory/'guard.py').exists()
    source_hash=hashlib.sha256(baseline.read_bytes()).hexdigest()
    off=load(baseline)
    async def main():return await execute(guarded),await execute(off)
    on_result,off_result=asyncio.run(main())
    assert on_result['effects_before_caller_confirmation']==0 and on_result['readback'],on_result
    assert off_result['effects_before_caller_confirmation']==1 and not off_result['readback'],off_result
    receipt={'framework':name,'mode':'offline scripted model; native SDK orchestration',
        'guarded':on_result,'prompt_only_countertest':off_result,
        'guard_diff_sha256':hashlib.sha256(diff).hexdigest(),'reconstructed_baseline_sha256':source_hash}
    output=TUTORIAL/'results'/name/'offline-contract-20261003'
    output.mkdir(parents=True,exist_ok=True)
    (output/'countertest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    subprocess.run(['patch','--fuzz=0','-p1'],input=diff,cwd=directory,check=True,capture_output=True)
    assert (directory/'agent.py').read_bytes()==(project/'agent.py').read_bytes()
    assert (directory/'guard.py').read_bytes()==(project/'guard.py').read_bytes()
    print('Source reconstruction and native SDK countertest verified')
    print(json.dumps(receipt))
