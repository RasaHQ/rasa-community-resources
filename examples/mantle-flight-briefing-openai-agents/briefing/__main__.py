"""Facilitator-only local replay service launcher; never called by import."""
import os

import uvicorn

from briefing.jobs import Jobs
from briefing.mcp_app import create_app
from briefing.replay import ReplayRunner


def main():
    # Read only the transport credential explicitly provided to this process.
    # No provider key lookup, persistence, token printing or secret discovery.
    token = os.environ.get("BRIEFING_MCP_TOKEN")
    if not token:
        raise SystemExit("Set the runtime-only BRIEFING_MCP_TOKEN in both facilitator processes")
    runner = ReplayRunner()
    app = create_app(Jobs(runner, replacement_plan=runner.replacement_plan,
                          ownership_mode="capability"), transport_token=token)
    uvicorn.run(app, host="127.0.0.1", port=8942, log_level="warning")


if __name__ == "__main__":
    main()
