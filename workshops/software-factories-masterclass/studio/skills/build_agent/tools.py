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
    if proc.returncode == 0:
        state = "candidate ready"
    elif proc.returncode == 3:
        state = (
            "candidate rejected: the hosted session finished and its specification failed the compiler's check, "
            "so nothing was built and no further result is coming"
        )
    else:
        state = "build uncertain; inspect runs before any retry"
    text = output.decode()
    spoken = [line[len("Spoken: "):] for line in text.splitlines() if line.startswith("Spoken: ")]
    if proc.returncode not in (0, 3) or not spoken:
        spoken = ["The build outcome is uncertain, so nothing is confirmed. Check the screen before trying again."]
    return ToolResult(llm_response={"state": state, "spoken": spoken[-1], "record": text[-3000:]})
