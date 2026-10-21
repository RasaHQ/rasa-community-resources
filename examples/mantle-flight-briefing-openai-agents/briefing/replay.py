"""Constructed classroom replay through Core's actual function-action loop.

This is a single named scenario, not a natural-language model or a recording
of a real flight. No provider or managed OpenAI request is made here.
"""
import asyncio
import re

from zeo_core.contracts.ui.widgets import TRANSFER_LABEL, DataRef
from zeo_core.integrations.agents import ScriptedTransport, function_tool, run

from briefing.data import instant, arrival_input, flight_payload, timeline_payload, weather_payload
from briefing.jobs import Answer, NeedsInput, Work

FETCHED_AT = "2026-10-22T12:00:00Z"


class ReplayRunner:
    @staticmethod
    def replacement_plan(change: str) -> tuple[str, ...] | None:
        return ("weather-hourly",) if change == "Replay DEMO101 morning weather" else None

    async def __call__(self, work: Work) -> Answer:
        # Missing-input scenarios remain explicitly named constructed replay.
        named = ("Replay DEMO101", "Replay DEMO101 later arrival", "Replay DEMO101 morning weather",
                 "Replay DEMO101 missing transfer", "Replay DEMO101 missing meeting", "Replay DEMO101 missing inputs",
                 "Replay DEMO101 flight unavailable", "Replay DEMO101 no estimate")
        inputs = dict(work.inputs or {"meeting_time": "2026-10-22T21:00:00Z", "transfer_minutes": 90})
        waiting = inputs.get("awaiting")
        if waiting and work.text not in named:
            if waiting == "transfer_minutes":
                match = re.fullmatch(r"([0-9]{1,4})(?: minutes?)?", work.text.strip())
                if match and 0 <= int(match[1]) <= 1440:
                    inputs[waiting] = int(match[1])
            else:
                try:
                    inputs[waiting] = instant(work.text).isoformat()
                except ValueError:
                    pass
            inputs.pop("awaiting", None)
        elif work.text in named:
            if work.text in ("Replay DEMO101 missing meeting", "Replay DEMO101 missing inputs"):
                inputs["meeting_time"] = None
            if work.text in ("Replay DEMO101 missing transfer", "Replay DEMO101 missing inputs"):
                inputs["transfer_minutes"] = None
            if work.text == "Replay DEMO101 later arrival":
                inputs["later"] = True
            elif work.text in ("Replay DEMO101", "Replay DEMO101 no estimate"):
                inputs["later"] = False
        else:
            raise ValueError("named_replay_scenario_required")
        for field, question in (("meeting_time", "What is the meeting time, including its date and timezone?"),
                                ("transfer_minutes", "What transfer duration in minutes should I assume?")):
            if inputs.get(field) is None:
                inputs["awaiting"] = field
                raise NeedsInput(field, question, inputs)
        return await asyncio.to_thread(self._run, work, inputs)

    def _run(self, work: Work, inputs: dict) -> Answer:
        later = inputs.get("later", False)
        raw_flight = {
            "ident_iata": "DEMO101", "origin": {"code_iata": "LHR"},
            "destination": {"code_iata": "JFK"},
            "scheduled_out": "2026-10-22T10:00:00Z", "estimated_out": None,
            "scheduled_in": "2026-10-22T17:00:00Z",
            "estimated_in": (None if work.text == "Replay DEMO101 no estimate" else
                             "2026-10-22T19:00:00Z" if later else "2026-10-22T17:30:00Z"),
            "terminal_destination": None, "status": "Classroom replay status",
        }
        unavailable = work.text == "Replay DEMO101 flight unavailable"
        flight = {} if unavailable else flight_payload(raw_flight)
        arrival, selected = (None, None) if unavailable else arrival_input(flight)
        weather = weather_payload({
            "timezone": "GMT", "utc_offset_seconds": 0,
            "hourly_units": {"temperature_2m": "°C", "precipitation_probability": "%", "precipitation": "mm"},
            "hourly": {"time": ["2026-10-22T17:00", "2026-10-22T18:00", "2026-10-22T19:00"],
                       "temperature_2m": [17, 16, 15], "precipitation_probability": [20, 25, 30],
                       "precipitation": [0, 0.1, 0.2]},
        }, location="New York — constructed scenario", arrival=arrival)
        if work.replaces == ("weather-hourly",):
            # Explicitly selected next-morning view, not the flight's arrival
            # forecast. No arrival marker is invented in this window.
            for hour, value in zip((6, 7, 8), weather["hourly"]):
                value["time"] = f"2026-10-23T{hour:02d}:00:00+00:00"
            weather["valid_from"] = "2026-10-23T06:00:00+00:00"
            weather["valid_to"] = "2026-10-23T09:00:00+00:00"
            weather["arrival_hour"] = None
        timeline = {} if unavailable else timeline_payload(arrival=arrival, meeting_time=inputs["meeting_time"], transfer_minutes=inputs["transfer_minutes"])
        if not unavailable:
            timeline["steps"][0]["label"] = f"Arrival from {selected}"
        errors = ({"flight_status": "Flight source unavailable in constructed replay",
                   "arrival_timeline": "Arrival timeline unavailable because flight source failed"}
                  if unavailable else {})
        payloads = {"flight_status": flight, "weather_hourly": weather, "arrival_timeline": timeline}
        if work.replaces == ("weather-hourly",):
            payloads = {"weather_hourly": weather}
        cards = {}

        def handler(component):
            def supply(arguments):
                if dict(arguments):
                    raise ValueError("unexpected_replay_arguments")
                assumptions = ([{"label": TRANSFER_LABEL, "value": inputs["transfer_minutes"], "kind": "assumption"}]
                               if component == "arrival_timeline" and component not in errors else [])
                reference = DataRef.model_validate({
                    "id": f"{component}-{work.request_id}",
                    "source": "Constructed classroom fixture; not a provider observation",
                    "fetched_at": FETCHED_AT, "as_of": None, "replay": True, "delayed": None,
                    "assumptions": assumptions, "payload": payloads[component],
                    "error": {"reason": errors[component]} if component in errors else None,
                })
                reference.check(component)
                cards[component] = reference
                return {"data_ref": reference.model_dump()}
            return supply

        handlers = {"read_" + component: handler(component) for component in payloads}
        tools = [function_tool(name, "Read the labelled constructed replay fixture",
                               {"type": "object", "properties": {}, "additionalProperties": False})
                 for name in handlers]
        turn = self._invoke(work, tools, handlers)
        return Answer(turn, cards, inputs=inputs)

    def _invoke(self, work, tools, handlers):
        turn_id = "replay-turn-" + work.request_id
        calls = [{"type": "function_call", "turn_id": turn_id,
                  "call_id": "call-" + name.removeprefix('read_'), "name": name, "arguments": {}}
                 for name in handlers]
        action = {"type": "agent.session.requires_action", "required_actions": calls}
        completed = [{"type": "agent.session.turn.output_text.done", "text": "Constructed REPLAY source cards ready."},
                     {"type": "agent.session.turn.completed"}]
        # The delivered Core pin submits a whole required-action batch in one
        # send, rather than opening one continuation stream per callback.
        scripts = ([action], completed)
        if work.session_id is None:
            transport = ScriptedTransport(*scripts, session_id="replay-" + work.request_id)
        else:
            # A continuation first receives input.message, then the same local
            # function-result loop. This remains a scripted, not remote, session.
            transport = ScriptedTransport(*scripts, session_id=work.session_id)
        turn = run(transport, agent={"tools": tools}, environment={}, text=work.text,
                   handlers=handlers, session_id=work.session_id)
        # Preserve actual callback records from this Core invocation, never
        # substitute a hand-built completed TurnResult.
        replies = [event for event in transport.sent if event["type"].endswith("tool_result")]
        if len(replies) != len(calls) or any(not event.get("success") for event in replies):
            raise ValueError("replay_tool_results_incomplete")
        return turn
