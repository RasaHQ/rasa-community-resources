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
import hashlib
import os
import sys
import time
import uuid
from pathlib import Path

from openai import OpenAI

# The model in OpenAI's Agents API quickstart. Change it with BUILDER_MODEL if you choose another.
MODEL = os.environ.get("BUILDER_MODEL", "gpt-6-astra")

# YOUR PART: edit these instructions. They are the builder's whole brief.
INSTRUCTIONS = """You are the builder in a small software factory.
You change one small thing and nothing else.
Write exactly one Python file and save it to /workspace/outputs/check_line_status.py.
The file holds only one function, with no imports and no other statements. A docstring is allowed.
The function has one statement: a return of a dictionary written out as plain values.
Say what you saved. Never write code that contacts a device or the network."""

TASK = """Add a read-only operation to a router helper: a function check_line_status() that takes no arguments
and returns the dictionary {"operation": "check_line_status", "status": "ok", "changes_anything": False}.
It must not send a restart or a factory reset, and it must not change any state."""

OUTPUT_PATH = "/workspace/outputs/check_line_status.py"
SCRATCH = Path("scratch")
# One build may not run longer than this, and one request to OpenAI may not wait longer than REQUEST_SECONDS.
# MAX_SECONDS is checked when an event arrives, so it is not a hard limit on the whole build: the last event can take up to
# REQUEST_SECONDS more, and the artifact download comes after it. Closing the stream does not confirm that the hosted session ended.
# Mantle waits 360 seconds (see the wiring README).
MAX_SECONDS = float(os.environ.get("BUILDER_MAX_SECONDS", "300"))
REQUEST_SECONDS = float(os.environ.get("BUILDER_REQUEST_SECONDS", "120"))


def build(task: str = TASK, show_events: bool = True) -> dict:
    """Run one builder session and download the file it saved. Returns a small summary, never a key.

    Each build gets its own folder under scratch/ and its own id, so two builds can never write the same file.
    The summary binds the result: the build id, the session id, and the sha256 of the saved file.
    """
    build_id = uuid.uuid4().hex[:12]
    folder = SCRATCH / f"build-{build_id}"
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / "check_line_status.py"
    deadline = time.monotonic() + MAX_SECONDS
    client = OpenAI(timeout=REQUEST_SECONDS, max_retries=0)
    summary = {"build_id": build_id, "saved": False, "builder_said": ""}
    with client.beta.agents.sessions.create(
        agent={"model": MODEL, "instructions": INSTRUCTIONS},
        environment={"type": "openai_hosted"},
        input=task,
        stream=True,
    ).with_result_collection() as stream:
        for event in stream:
            if show_events:
                print(event.to_json(indent=None), flush=True)
            if time.monotonic() > deadline:
                summary["builder_said"] = f"The build ran longer than {MAX_SECONDS:.0f} seconds and was stopped."
                return summary
        result = stream.get_final_result()
    summary.update(session_id=result.session_id, builder_said=result.output_text)
    for artifact in client.beta.agents.sessions.artifacts.list(result.session_id):
        if artifact.path != OUTPUT_PATH:
            continue
        with client.beta.agents.sessions.artifacts.with_streaming_response.content(
            artifact.id, session_id=result.session_id
        ) as response:
            response.stream_to_file(destination)
        summary.update(saved=True, file=str(destination), sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    return summary


if __name__ == "__main__":
    if not os.environ.get("OPENAI_API_KEY"):
        sys.exit("Set the OPENAI_API_KEY Codespaces secret for this repository, then restart the codespace.")
    outcome = build()
    print("\nsaved:", outcome["saved"], outcome.get("file", ""), outcome.get("sha256", ""))
    print("builder said:", outcome["builder_said"])
