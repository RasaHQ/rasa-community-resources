"""Dispatch every casebook adapter through the installed SDK calling convention."""
import asyncio
import importlib.util
import os
from pathlib import Path
import tempfile
import sys
sys.path.insert(0, str(Path.cwd()))
from casebook import load_case, execute
from rasa.mantle.tools.result import ToolResult

async def main():
    spec=importlib.util.spec_from_file_location('case_tools',Path('tools/cases.py'))
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    cases=sorted(Path('examples').glob('*.json'))
    assert len(cases)==62
    with tempfile.TemporaryDirectory() as tmp:
        os.environ['CASEBOOK_DATABASE']=str(Path(tmp)/'sdk.sqlite')
        os.environ['CASEBOOK_RUN_ID']='sdk-compatibility'
        for path in cases:
            case=load_case(path.stem)
            expected=execute(case,case['facts'],'oracle-'+path.stem,Path(tmp)/'oracle.sqlite')
            result=await module.rehearse_case(case_id=path.stem,context=None)
            assert isinstance(result,ToolResult)
            assert result.llm_response['status']==expected['status'],path.stem
        unknown=await module.rehearse_case(case_id='../not-a-case',context=None)
        assert unknown.llm_response=={'status':'blocked','reason':'unsupported_lab_input'}
    print('62 real SDK adapters match deterministic case outcomes; unknown identifier blocked')

asyncio.run(main())
