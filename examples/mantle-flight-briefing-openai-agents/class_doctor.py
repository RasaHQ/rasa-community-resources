"""Environment-only class readiness; live proof runs only on the facilitator."""
import argparse
import asyncio
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import re

from briefing.native_runtime import UnsupportedAgentsSDK, native_turn

ROOT = Path(__file__).parent
KEYS = {'openai': 'OPENAI_API_KEY', 'anthropic': 'ANTHROPIC_API_KEY'}


def selected_provider(project=ROOT / 'project'):
    text = (project / 'integrations.yml').read_text()
    match = re.search(r'^llm:\s*\n\s+model_group:\s*(openai|anthropic)\s*$', text, re.M)
    if not match:
        raise ValueError('Select openai or anthropic in llm.model_group.')
    return match[1]


async def probe_mantle(project):
    # Normal engine entry-point import order; no fixture substitution here.
    from rasa.core.agent import Agent
    from rasa.mantle.llm.client import LLMClient
    from rasa.mantle.model_archive.bootstrap import ModelBootstrap, resolve_integration_llm_config
    client = LLMClient.from_bootstrap(ModelBootstrap(llm=dict(resolve_integration_llm_config(project))))
    reply = await asyncio.wait_for(client.acompletion(
        [{'role': 'user', 'content': 'Reply with READY only.'}]), timeout=60)
    return bool(reply.response_text())


def probe_agents():
    from openai import OpenAI
    # Default SDK auth reads OPENAI_API_KEY only in this facilitator process.
    with OpenAI(timeout=20, max_retries=0) as client:
        result = native_turn(client, agent={'model': os.environ.get('BRIEFING_AGENTS_MODEL', 'gpt-4.1-mini'),
            'instructions': 'Reply with READY only; no tools or files.'},
            text='Reply with READY only.')
        return result.ok


def main(argv=None):
    os.environ['LITELLM_MODE'] = 'PRODUCTION'
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            # argparse normally echoes unknown values; a pasted credential must
            # not become an error message or traceback.
            raise ValueError('invalid_doctor_options')

    parser = SafeParser(description=__doc__)
    parser.add_argument('--scripted', action='store_true', help='Select the labelled keyless fallback')
    parser.add_argument('--probe', action='store_true', help='Make one live selected-provider smoke call')
    parser.add_argument('--probe-agents', action='store_true', help='Make one live OpenAI managed Agents turn')
    try:
        args = parser.parse_args(argv)
    except ValueError:
        print('Refused: use only the documented doctor options; supply keys in the environment.')
        return 2
    for name in KEYS.values():
        print(name + ': ' + ('SET' if os.environ.get(name, '').strip() else 'MISSING'))
    if args.probe and args.probe_agents:
        print('Refused: select one live probe per invocation.')
        return 2
    if args.scripted:
        if args.probe or args.probe_agents:
            print('Refused: SCRIPTED does not make live calls.')
            return 2
        print('PATH: SCRIPTED — project/.venv/bin/python scripted_demo.py')
        return 0
    if not args.probe and not args.probe_agents and not any(
            os.environ.get(name, '').strip() for name in KEYS.values()):
        print('PATH: SCRIPTED — project/.venv/bin/python scripted_demo.py')
        return 0
    try:
        provider = 'openai' if args.probe_agents else selected_provider()
    except (ValueError, OSError):
        print('Refused: select openai or anthropic in project/integrations.yml llm.model_group.')
        return 2
    key_name = KEYS[provider]
    if not os.environ.get(key_name, '').strip():
        print('PATH: SCRIPTED (live ' + provider.upper() + ' unavailable)')
        print('Refused: set ' + key_name + ' in this process environment for the live path.')
        return 2
    if len(os.environ[key_name].strip()) < 16:
        print('Refused: selected environment key is not a usable credential.')
        return 2
    if any(os.environ.get(name, '').strip() for name in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL')):
        print('Refused: custom provider base URL environment is SET; this kit supports provider defaults only.')
        return 2
    print('PATH: live ' + provider.upper() + (' managed Agents' if args.probe_agents else ' Mantle'))
    if args.probe or args.probe_agents:
        # Never print response content, provider exceptions or diagnostic dumps.
        try:
            with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
                from project.lib.capability_logging import install
                install()
                ok = probe_agents() if args.probe_agents else asyncio.run(probe_mantle(ROOT / 'project'))
        except UnsupportedAgentsSDK:
            print('Refused: the worker SDK lacks client.beta.agents.sessions; use its locked environment.')
            return 2
        except Exception:
            print('PROBE: FAILED — check provider access and supported runtime; raw diagnostics suppressed.')
            return 1
        print('PROBE: ' + ('PASS' if ok else 'FAILED — no inspected completed output'))
        return 0 if ok else 1
    print('Readiness only; no live call made. Use --probe in the facilitator environment.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
