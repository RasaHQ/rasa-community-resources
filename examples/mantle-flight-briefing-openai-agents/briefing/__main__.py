from demo_host import runtime_ports
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
    modes.add_argument('--factory-baseline', action='store_true',
                       help='Opt-in three public-source cards; no market request')
    modes.add_argument('--factory-received', metavar='RECEIVING_DIR',
                       help='Three public-source cards plus the fixed reviewed staged market module')
    parser.add_argument('--host', default=os.environ.get('BRIEFING_VIEWER_HOST', '127.0.0.1'))
    args = parser.parse_args()
    from demo_host import require_viewer_access
    require_viewer_access(args.host)
    managed_sources = (args.public_sources and bool(os.environ.get('OPENAI_API_KEY', '').strip())
                       and bool(os.environ.get('BRIEFING_AGENTS_MODEL', '').strip()))
    if (args.live_model or managed_sources) and any(os.environ.get(name, '').strip()
                               for name in ('OPENAI_BASE_URL', 'ANTHROPIC_BASE_URL')):
        raise SystemExit('Refused: custom provider base URL environment is SET; this kit supports provider defaults only.')
    # Read only the transport credential explicitly provided to this process.
    # No provider key lookup, persistence, token printing or secret discovery.
    token = os.environ.get("BRIEFING_MCP_TOKEN")
    if not token:
        raise SystemExit("Set the runtime-only BRIEFING_MCP_TOKEN in both facilitator processes")
    runner = ReplayRunner()
    factory_mode = args.factory_baseline or args.factory_received is not None
    public_mode = args.public_sources or factory_mode
    if public_mode:
        try:
            if factory_mode:
                from briefing.factory_runner import FactoryRunner
                runner = FactoryRunner(received_directory=args.factory_received)
            else:
                from briefing.public_sources import PublicSourcesRunner
                runner = PublicSourcesRunner()
        except ImportError:
            raise SystemExit('Public sources need the reviewed adapter release; update the locked Core pin after it is published.') from None
    if args.live_model or managed_sources:
        from briefing.live import LiveFixtureRunner
        from briefing.live_public_sources import LivePublicSourcesRunner
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
        if managed_sources:
            runner.close()
            runner = LivePublicSourcesRunner(client_factory, model=model)
        else:
            runner = LiveFixtureRunner(client_factory, model=model)
    try:
        app = create_app(Jobs(runner, replacement_plan=runner.replacement_plan,
                              ownership_mode="capability"), transport_token=token, host=args.host)
        uvicorn.run(app, host=args.host, port=runtime_ports()[0], log_level="warning")
    finally:
        if public_mode:
            runner.close()


if __name__ == "__main__":
    main()
