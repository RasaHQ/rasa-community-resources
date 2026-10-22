"""Facilitator-only local service; live model mode is an explicit opt-in."""
import argparse
import os

import uvicorn

from briefing.jobs import Jobs
from briefing.mcp_app import create_app
from briefing.replay import ReplayRunner


def main():
    os.environ['LITELLM_MODE'] = 'PRODUCTION'
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise SystemExit('Use only --live-model; supply credentials in the facilitator environment.')

    parser = SafeParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--public-sources', action='store_true',
                       help='SCRIPTED tool control with real keyless public source references')
    modes.add_argument('--live-model', action='store_true',
                        help='Real managed model with constructed REPLAY source fixtures')
    args = parser.parse_args()
    if args.live_model and any(os.environ.get(name, '').strip()
                               for name in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL')):
        raise SystemExit('Refused: custom provider base URL environment is SET; this kit supports provider defaults only.')
    # Read only the transport credential explicitly provided to this process.
    # No provider key lookup, persistence, token printing or secret discovery.
    token = os.environ.get("BRIEFING_MCP_TOKEN")
    if not token:
        raise SystemExit("Set the runtime-only BRIEFING_MCP_TOKEN in both facilitator processes")
    runner = ReplayRunner()
    if args.public_sources:
        try:
            from briefing.public_sources import PublicSourcesRunner
            runner = PublicSourcesRunner()
        except ImportError:
            raise SystemExit('Public sources need the reviewed adapter release; update the locked Core pin after it is published.') from None
    if args.live_model:
        from briefing.live import LiveFixtureRunner
        from openai import OpenAI
        from briefing.native_runtime import require_agents_sessions
        model = os.environ.get('BRIEFING_AGENTS_MODEL', '').strip()
        if not model:
            raise SystemExit('Set BRIEFING_AGENTS_MODEL in the facilitator environment')
        # Read credentials only in the expressly selected facilitator path.
        def client_factory():
            client = OpenAI(timeout=20, max_retries=0)
            try:
                require_agents_sessions(client)
            except Exception:
                client.close()
                raise
            return client
        runner = LiveFixtureRunner(client_factory, model=model)
    app = create_app(Jobs(runner, replacement_plan=runner.replacement_plan,
                          ownership_mode="capability"), transport_token=token)
    try:
        uvicorn.run(app, host="127.0.0.1", port=8942, log_level="warning")
    finally:
        if args.public_sources:
            runner.close()


if __name__ == "__main__":
    main()
