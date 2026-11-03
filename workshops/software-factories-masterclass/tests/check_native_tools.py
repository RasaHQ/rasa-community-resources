"""Offline native invocation regression; run with ~/.venv-mantle/bin/python.

Uses Mantle's actual ToolInvoker (including its context injection, return
validation and serialization). Tracker/provider/subprocess doubles keep this
probe offline: it starts no LLM, Deepgram or hosted Agents session.

Optional --root points at another workshop tree for a baseline negative control.
"""
import argparse
import asyncio
from contextlib import nullcontext
import importlib.util
import json
import os
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, patch

from rasa.mantle.llm.tool_schemas import resolve_builder_tool_schema
from rasa.mantle.orchestration.tool_execution.invoker import ToolInvoker


class OfflineTracker:
    def memory_scope(self):
        return ("travel_briefing", "main")

    def recording_write(self, **_):
        return nullcontext()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# A flight-briefing agent forecasts a landing from the flight number and date; the starter takes an airport and a time.
ARRIVAL_WEATHER_ARGS = {"flight_number": "ZZ201", "flight_date": "2026-11-03"}
ARRIVAL_WEATHER_READ = ["", "", "ZZ201", "2026-11-03"]

ARGS = {
    "destination_weather": {"airport_code": "LHR", "arrival_time": ""},
    "convert_currency": {"base": "USD", "quote": "GBP", "amount": 200.0},
    "tonight_departures": {"origin": "OSL", "destination": "BGO"},
    "flight_status": {"flight_number": "ZZ201"},
}


async def check(root):
    build = load("native_probe_build", root / "factory/build.py")
    invoker = ToolInvoker(
        mcp_runtime=None, tool_timeout=5, verbatim_trigger_evaluator=None
    )
    tracker = OfflineTracker()
    results = []

    async def invoke(label, module, name, arguments, expected):
        func = getattr(module, name)
        schema = resolve_builder_tool_schema(
            skill_id="travel_briefing", tool_name=name,
            tool_func=func, mcp_runtime=None,
        )
        assert schema is not None
        assert "context" not in schema.parameters.get("properties", {})
        assert invoker.validate_builder_tool_arguments(
            "travel_briefing", name, func, arguments
        ) is None
        raw = await invoker.call_tool_func(func, name, arguments, tracker)
        actual = json.loads(raw)
        ok = actual == expected
        results.append({"project": label, "tool": name, "pass": ok,
                        "result": actual})

    with tempfile.TemporaryDirectory() as directory:
        projects = []
        for spec in ("starter", "full"):
            out = Path(directory) / spec
            build.generate((root / "reference" / (spec + ".json")).read_bytes(), out)
            projects.append(("generated-" + spec, out))
        projects.append(("shipped-reference", root / "reference/finished-agent"))
        for label, project in projects:
            module = load(label.replace("-", "_"),
                          project / "skills/travel_briefing/tools.py")
            names = {n for n in ARGS if hasattr(module, n)}
            expected_names = set(ARGS) if label != "generated-starter" else {
                "destination_weather", "convert_currency"
            }
            assert names == expected_names, (label, names)
            calls = []

            def reader(kind, *arguments):
                calls.append((kind, list(arguments)))
                return {"offline_native_probe": True, "kind": kind,
                        "arguments": list(arguments)}

            with patch.object(module, "read", side_effect=reader):
                for key in ("weather", "fx", "flights", "status"):
                    name, _, _, _ = build.TOOLS[key]
                    if name not in names:
                        continue
                    arrival_mode = name == "destination_weather" and label != "generated-starter"
                    arguments = ARRIVAL_WEATHER_ARGS if arrival_mode else ARGS[name]
                    read_arguments = ARRIVAL_WEATHER_READ if arrival_mode else list(arguments.values())
                    expected = {"offline_native_probe": True, "kind": key,
                                "arguments": read_arguments}
                    before = len(calls)
                    await invoke(label, module, name, arguments, expected)
                    if results[-1]["pass"]:
                        assert calls[before:] == [(key, read_arguments)]
        studio = load("native_probe_studio", root / "studio/skills/build_agent/tools.py")

        class OfflineProcess:
            returncode = 0

            async def communicate(self):
                return (b'{"OFFLINE_PROBE_NO_HOSTED_SESSION":true}\nSpoken: Offline probe, no hosted session.\n', b"")

        proc = AsyncMock(return_value=OfflineProcess())
        with patch.dict(os.environ, {"TRAVEL_FACTORY_ROOT": str(root)}), \
                patch.object(studio.asyncio, "create_subprocess_exec", proc):
            await invoke(
                "studio", studio, "propose_travel_agent", {"brief": "Offline probe"},
                {"state": "candidate ready",
                 "spoken": "Offline probe, no hosted session.",
                 "record": '{"OFFLINE_PROBE_NO_HOSTED_SESSION":true}\nSpoken: Offline probe, no hosted session.\n'},
            )
            if results[-1]["pass"]:
                proc.assert_awaited_once()
                assert proc.await_args.args == (
                    str(Path.home() / ".venv-builder/bin/python"),
                    str(root / "factory/build.py"), "propose", "hosted", "Offline probe",
                )
    assert len(results) == 11
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    results = asyncio.run(check(args.root.resolve()))
    print(json.dumps({"mode": "OFFLINE_NATIVE_TOOL_PROBE_NO_PAID_CALLS",
                      "calls": len(results), "results": results}, indent=2))
    raise SystemExit(0 if all(row["pass"] for row in results) else 1)
