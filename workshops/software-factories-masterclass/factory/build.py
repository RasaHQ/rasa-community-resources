"""Build and inspect a travel Mantle project. Each run has its own output."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    "weather": (
        "destination_weather",
        "airport_code: str, arrival_time: str",
        "airport_code, arrival_time",
        "Forecast at an airport. Use an ISO timestamp with offset, or an empty string for the current hour.",
    ),
    "fx": (
        "convert_currency",
        "base: str, quote: str, amount: float",
        "base, quote, amount",
        "Convert an amount using a dated reference exchange rate.",
    ),
    "flights": (
        "tonight_departures",
        "origin: str, destination: str",
        "origin, destination",
        "List remaining scheduled departures tonight in the departure airport time zone.",
    ),
    "status": (
        "flight_status",
        "flight_number: str",
        "flight_number",
        "Look up flight records by IATA flight number; distinguish scheduled and estimated arrival.",
    ),
}
TASK = """Create a Rasa Mantle travel agent specification for this brief. Return a JSON object with exactly these keys: name (lowercase slug), description (one sentence routing description), instructions (plain text skill guidance), tools (array drawn from weather, fx, flights, status). The full travel desk needs all four. Keep to these limits: name 2 to 49 characters of lowercase letters, digits and hyphens starting with a letter; description one sentence under 300 characters; instructions plain text of at most 2000 characters (the compiler rejects anything over 2500); the whole JSON file under 16 KB. Write short, specific instructions. Clarify ambiguous airports, use flight status to establish arrival time before an arrival forecast, use the departure airport's local evening and cite providers and dates. Do not invent data or bookings."""
RULES = """Speak in short turns. Read airport names and currencies clearly. Ask one clarification at a time. Supported airports are OSL, BGO, JFK, LHR, CDG, MAD and MEX (flight tools cover only Oslo–Bergen in either direction). Flight status uses the arrival board; never treat a departure timestamp as arrival. When flight records share a number, ask which date and route the traveler means. Clarify origin, destination, flight number or time when ambiguous. Obtain a tool result for every external fact. State provider, time or rate date and coverage. If unavailable, say which fact is unavailable and continue with other tools. An empty or partial board does not establish that no flights exist. Never claim seats or bookings. For weather at landing, use estimated arrival if supplied, otherwise scheduled arrival, and identify which you used. If neither is known ask for a time. Keep estimates, forecasts and observed facts distinct."""


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def validate(raw):
    import re

    if len(raw) > 16000:
        raise ValueError("Specification exceeds 16 KB")
    s = json.loads(raw)
    if not isinstance(s, dict) or set(s) != {
        "name",
        "description",
        "instructions",
        "tools",
    }:
        raise ValueError("Expected four specification fields")
    if not isinstance(s["name"], str) or not re.fullmatch(
        "[a-z][a-z0-9-]{1,48}", s["name"]
    ):
        raise ValueError("Invalid agent name")
    for k in ("instructions", "description"):
        if not isinstance(s[k], str) or not 10 <= len(s[k]) <= 2500:
            size = len(s[k]) if isinstance(s[k], str) else type(s[k]).__name__
            raise ValueError(f"Invalid {k}: {size} characters, allowed 10 to 2500")
    if (
        not isinstance(s["tools"], list)
        or not s["tools"]
        or not all(isinstance(k, str) and k in TOOLS for k in s["tools"])
        or len(set(s["tools"])) != len(s["tools"])
    ):
        raise ValueError("Unknown, empty or duplicate tool selection")
    return s


def generate(raw, out):
    spec = validate(raw)
    if out.exists():
        raise ValueError("Choose a new output directory")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=out.parent) as tmp:
        project = Path(tmp) / "project"
        skill = project / "skills" / "travel_briefing"
        skill.mkdir(parents=True)
        (project / "agent.yml").write_text(
            "agent:\n  id: "
            + json.dumps(spec["name"])
            + "\n  language: en\n  persona: You are a travel desk assistant.\nrules:\n  - "
            + json.dumps(RULES)
            + "\n"
        )
        shutil.copy(ROOT / "reference/integrations.yml", project / "integrations.yml")
        body = (
            spec["instructions"]
            + "\n\n"
            + RULES
            + "\n\n"
            + "\n".join(
                "Use @tool." + TOOLS[k][0] + " to " + TOOLS[k][3] for k in spec["tools"]
            )
        )
        (skill / "skill.md").write_text(
            "---\nname: Travel briefing\ndescription: "
            + json.dumps(spec["description"])
            + "\n---\n\n"
            + body
            + "\n"
        )
        source = (ROOT / "travel_data.py").read_text().split("if __name__")[0]
        source += "\nimport asyncio\nfrom rasa.mantle.tools.decorator import ToolContext, tool\nfrom rasa.mantle.tools.result import ToolResult\n"
        for k in spec["tools"]:
            name, params, args, doc = TOOLS[k]
            source += f"\n@tool(description={doc!r})\nasync def {name}(context: ToolContext, {params}) -> ToolResult:\n    data = await asyncio.to_thread(read, {k!r}, {args})\n    return ToolResult(llm_response=data)\n"
        compile(source, "tools.py", "exec")
        (skill / "tools.py").write_text(source)
        project.rename(out)


def propose(mode, brief):
    run = ROOT / "runs" / uuid.uuid4().hex
    run.mkdir(parents=True)
    dest = run / "agent.json"
    session = None
    if mode == "sample":
        shutil.copy(ROOT / "reference/full.json", dest)
    elif mode == "codex":
        subprocess.run(
            [
                "codex",
                "exec",
                "--sandbox",
                "read-only",
                "--skip-git-repo-check",
                "--output-last-message",
                str(dest),
                TASK
                + "\nBrief: "
                + brief
                + "\nOutput raw JSON only, without a Markdown fence.",
            ],
            cwd=run,
            check=True,
        )
    else:
        from openai import OpenAI

        client = OpenAI(timeout=90, max_retries=0)
        deadline = time.monotonic() + 360
        with client.beta.agents.sessions.create(
            agent={
                "model": os.getenv("BUILDER_MODEL", "gpt-6-astra"),
                "instructions": TASK + " Save only /workspace/outputs/agent.json.",
            },
            environment={"type": "openai_hosted"},
            input=brief,
            stream=True,
        ).with_result_collection() as stream:
            for _ in stream:
                if time.monotonic() > deadline:
                    raise TimeoutError(
                        "Stopped waiting for hosted events; remote outcome uncertain. Keep "
                        + str(run)
                    )
            session = stream.get_final_result().session_id
        (run / "session.txt").write_text(session)
        print("Hosted session:", session, flush=True)
        for art in client.beta.agents.sessions.artifacts.list(session):
            if art.path == "/workspace/outputs/agent.json":
                with (
                    client.beta.agents.sessions.artifacts.with_streaming_response.content(
                        art.id, session_id=session
                    ) as response
                ):
                    response.stream_to_file(dest)
                break
    if not dest.exists():
        raise ValueError("No candidate in " + str(run))
    raw = dest.read_bytes()
    receipt = {
        "mode": mode,
        "session": session,
        "candidate": str(dest),
        "sha256": digest(raw),
    }
    (run / "receipt.json").write_text(json.dumps(receipt, indent=2))
    try:
        spec = validate(raw)
        if set(spec["tools"]) != set(TOOLS):
            raise ValueError("Full desk requires all four tools")
    except ValueError as error:
        # The session finished and the file was downloaded; only the compiler's check failed. Say exactly that.
        receipt.update(outcome="invalid_candidate", reason=str(error))
        (run / "receipt.json").write_text(json.dumps(receipt, indent=2))
        print(json.dumps(receipt, indent=2))
        print("Candidate rejected by the compiler:", error, "- kept in", run.relative_to(ROOT), flush=True)
        raise SystemExit(3)
    print(json.dumps(receipt, indent=2))
    print("Review:", dest)
    print("Run directory:", run.relative_to(ROOT))
    return run


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="op", required=True)
    q = sub.add_parser("propose")
    q.add_argument("mode", choices=["sample", "codex", "hosted"])
    q.add_argument(
        "brief", nargs="?", default="Build the four-tool Oslo to Bergen travel desk."
    )
    q = sub.add_parser("approve")
    q.add_argument("run", type=Path)
    q.add_argument("output", type=Path)
    q = sub.add_parser("starter")
    q.add_argument("output", type=Path)
    a = p.parse_args()
    if a.op == "propose":
        propose(a.mode, a.brief)
    elif a.op == "starter":
        generate((ROOT / "reference/starter.json").read_bytes(), a.output)
    else:
        raw = (a.run / "agent.json").read_bytes()
        receipt = json.loads((a.run / "receipt.json").read_text())
        if digest(raw) != receipt["sha256"]:
            raise ValueError("Candidate changed since receipt")
        if set(validate(raw)["tools"]) != set(TOOLS):
            raise ValueError("Full desk requires all four tools")
        generate(raw, a.output)
        print("Built", a.output)


if __name__ == "__main__":
    main()
