"""Exercise real Mantle adapters without calling a model or external service."""
import asyncio
import os
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from casebook import ROOT, count_effects, load_case
from tools.cases import rehearse_case, inspect_case, record_case_intake
from rasa.mantle.validation import validate_project


async def check():
    validate_project(ROOT)
    with tempfile.TemporaryDirectory() as folder:
        database = Path(folder) / 'adapter.sqlite'
        os.environ['CASEBOOK_DATABASE'] = str(database)
        os.environ['CASEBOOK_RUN_ID'] = 'adapter-check'
        for path in sorted((ROOT / 'examples').glob('*.json')):
            first = (await rehearse_case(path.stem)).llm_response
            second = (await inspect_case(path.stem)).llm_response
            assert first['status'] == 'succeeded'
            assert second['replay'] is True
            assert first['reference'] == second['reference']
            if load_case(path.stem).get('intakeKind'):
                intake = (await record_case_intake(path.stem)).llm_response
                assert intake['status'] == 'recorded' and intake['effects'] == 0
        assert count_effects(database) == 62
        assert (await rehearse_case('../unsafe')).llm_response['status'] == 'blocked'
    print('Validated Mantle project and real SDK adapters for 62 cases plus four independent intakes. No model or external service called.')


asyncio.run(check())
