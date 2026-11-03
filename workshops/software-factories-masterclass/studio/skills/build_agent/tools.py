import asyncio
import os
from pathlib import Path
from rasa.mantle.tools.decorator import ToolContext, tool
from rasa.mantle.tools.result import ToolResult


@tool(
    description="Start one hosted session to propose a four-tool Mantle travel agent."
)
async def propose_travel_agent(context: ToolContext, brief: str) -> ToolResult:
    root = Path(os.environ["TRAVEL_FACTORY_ROOT"])
    proc = await asyncio.create_subprocess_exec(
        str(Path.home() / ".venv-builder/bin/python"),
        str(root / "factory/build.py"),
        "propose",
        "hosted",
        brief,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
    )
    output, _ = await proc.communicate()
    return ToolResult(
        llm_response={
            "state": "candidate ready"
            if proc.returncode == 0
            else "build uncertain; inspect runs before any retry",
            "receipt": output.decode()[-3000:],
        }
    )
