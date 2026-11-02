"""Your builder agent, made with the OpenAI Agents API.

You choose the model and write the instructions. The agent works in OpenAI's hosted sandbox: it writes a file,
runs it, and saves it under /workspace/outputs. This script watches the session and downloads the file into a
scratch folder. It never touches the router helper's own files.

Run it:  python3 builder.py
Needs:   pip install --upgrade openai   and an OpenAI key in OPENAI_API_KEY with the permissions
         api.agents.read, api.agents.write and api.responses.write (OpenAI's Agents API quickstart).

Not run yet by anyone for this workshop. The calls follow OpenAI's Agents API quickstart and its page on files
and artifacts, both read on Nov 2.
"""
import os
import sys
from pathlib import Path

from openai import OpenAI

# The model in OpenAI's Agents API quickstart. Change it with BUILDER_MODEL if you choose another.
MODEL = os.environ.get("BUILDER_MODEL", "gpt-6-astra")

# YOUR PART: edit these instructions. They are the builder's whole brief.
INSTRUCTIONS = """You are the builder in a small software factory.
You change one small thing and nothing else.
Write exactly one Python file and save it to /workspace/outputs/check_line_status.py.
Run it once to make sure it works, then say what you ran and what it printed.
Never change a command table. Never write code that contacts a device or the network."""

TASK = """Add a read-only operation to a router helper: a function check_line_status() that takes no arguments
and returns the dictionary {"operation": "check_line_status", "status": "ok", "changes_anything": False}.
It must not send a restart or a factory reset, and it must not change any state."""

OUTPUT_PATH = "/workspace/outputs/check_line_status.py"
DESTINATION = Path("scratch/check_line_status.py")


def build(task: str = TASK, show_events: bool = True) -> dict:
    """Run one builder session and download the file it saved. Returns a small summary, never a key."""
    client = OpenAI()
    with client.beta.agents.sessions.create(
        agent={"model": MODEL, "instructions": INSTRUCTIONS},
        environment={"type": "openai_hosted"},
        input=task,
        stream=True,
    ).with_result_collection() as stream:
        for event in stream:
            if show_events:
                print(event.to_json(indent=None), flush=True)
        result = stream.get_final_result()
    summary = {"session_id": result.session_id, "builder_said": result.output_text, "saved": False}
    DESTINATION.parent.mkdir(parents=True, exist_ok=True)
    for artifact in client.beta.agents.sessions.artifacts.list(result.session_id):
        if artifact.path != OUTPUT_PATH:
            continue
        with client.beta.agents.sessions.artifacts.with_streaming_response.content(
            artifact.id, session_id=result.session_id
        ) as response:
            response.stream_to_file(DESTINATION)
        summary.update(saved=True, file=str(DESTINATION))
    return summary


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set the OPENAI_API_KEY Codespaces secret for this repository, then restart the codespace.")
    outcome = build()
    print("\nsaved:", outcome["saved"], outcome.get("file", ""))
    print("builder said:", outcome["builder_said"])
