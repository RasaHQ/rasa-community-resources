"""Reproduce two SDK input changes against localhost, without extra environments.

Run with the selected framework's locked interpreter. Copies only agent.py and
its guard into a temporary source directory; shares no mutable conversation.
"""
from pathlib import Path
import ast
import hashlib
import json
import os
import subprocess
import sys
import tempfile

T = Path(__file__).resolve().parents[2]
name = sys.argv[1]
if name not in {'crewai', 'livekit'}:
    raise SystemExit('Choose crewai or livekit')
project = T / name
original = (project / 'agent.py').read_text()
if name == 'crewai':
    tree = ast.parse(original)
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'ClinicResponses')
    lines = original.splitlines(keepends=True)
    modified = ''.join(lines[:cls.lineno - 1]) + 'class ClinicResponses(OpenAICompletion):\n    pass\n' + ''.join(lines[cls.end_lineno:])
    change = 'Remove only the provider-schema preservation override'
else:
    needle = "raw_schema=clinic.json_schema(name), on_duplicate='allow'"
    assert original.count(needle) == 1
    modified = original.replace(needle, needle + ', flags=llm.ToolFlag.CANCELLABLE')
    change = 'Enable ToolFlag.CANCELLABLE on the existing raw-schema tools'
with tempfile.TemporaryDirectory(prefix='cedar-sdk-input-drift-') as scratch:
    scratch = Path(scratch)
    (scratch / 'agent.py').write_text(modified)
    (scratch / 'guard.py').write_bytes((project / 'guard.py').read_bytes())
    driver_path = T / 'shared/spec/verify_provider_contract.py'
    driver = '__file__ = ' + repr(str(driver_path)) + '\n' + driver_path.read_text()
    driver = driver.replace("sys.path.insert(0,str(T/name))", "sys.path.insert(0," + repr(str(scratch)) + ")")
    driver = driver.replace("  assert schemas=={n:clinic.json_schema(n)['parameters'] for n in clinic.TOOL_SPECS},schemas", "  assert schemas!={n:clinic.json_schema(n)['parameters'] for n in clinic.TOOL_SPECS}\n  print('DRIFT_CAPTURE '+json.dumps({'path':row['path'],'model':body['model'],'reasoning':body['reasoning'],'tools':body['tools']}),flush=True)")
    # Do not overwrite the passing provider-contract receipt with this condition.
    driver = driver[:driver.index(" receipt={'framework'")] + '\nfinally:server.shutdown();server.server_close()\n'
    proc = subprocess.run([sys.executable, '-c', driver, name], cwd=project, env={k:v for k,v in os.environ.items() if not k.endswith('_API_KEY') and 'LICENSE' not in k}, text=True, capture_output=True, timeout=30)
    if proc.returncode:
        raise SystemExit(proc.stderr)
    capture = json.loads(next(line.removeprefix('DRIFT_CAPTURE ') for line in proc.stdout.splitlines() if line.startswith('DRIFT_CAPTURE ')))
    schemas = {tool['name']: tool['parameters'] for tool in capture['tools']}
    if name == 'livekit':
        assert set(schemas) - {'verify_patient','select_medication','send_refill_request','check_request_status','route_clinical_question'} == {'lk_agents_cancel_task','lk_agents_get_running_tasks'}
    else:
        assert schemas['send_refill_request']['required'] == ['record_id','patient_note']
        assert schemas['route_clinical_question']['required'] == ['question','record_id']
    receipt = {'framework':name,'condition':'production SDK against localhost fake provider; no model spend','source_change':change,
        'guarded_agent_sha256':hashlib.sha256(original.encode()).hexdigest(),'probe_agent_sha256':hashlib.sha256(modified.encode()).hexdigest(),
        'source_copy_only':True,'extra_environment':False,'observed_provider_request':capture}
    out = T/'results'/name/'offline-contract-20261003/provider-drift.json'
    out.write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'framework':name,'provider_tools':list(schemas),'schema_drift_reproduced':True}))
