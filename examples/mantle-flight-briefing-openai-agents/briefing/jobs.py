"""Conversation-owned jobs; Core owns turn success and widget validation.

Run this service in the resource-owned Python 3.12 MCP worker with the
approved Core wheel. The transport supplies Owner from authenticated context;
it must never construct Owner from the public tool's arguments.
"""
from __future__ import annotations

import asyncio
import secrets
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Awaitable, Callable
from uuid import uuid4

from zeo_core.contracts.ui.widgets import DataRef, WidgetBoard, WidgetUpsert
from zeo_core.integrations.agents import TurnResult

from briefing.identity import conversation_identity
from project.lib.capability_logging import install as install_log_redaction


class BriefingRefused(ValueError):
    """Public coded refusal, without source data or provider exception text."""


class NeedsInput(ValueError):
    """A runner needs an explicit traveller answer before doing more work."""

    def __init__(self, field: str, question: str, inputs: dict):
        if field not in ("meeting_time", "transfer_minutes"):
            raise ValueError("unsupported_input_field")
        if not isinstance(question, str) or not question.strip() or len(question) > 200 or any(
            part in question for part in ("<", ">", "://", "\x00")
        ):
            raise ValueError("invalid_input_question")
        super().__init__("traveller_input_required")
        self.field, self.question, self.inputs = field, question, deepcopy(inputs)


@dataclass(frozen=True)
class Owner:
    peer: str
    conversation: str

    def __post_init__(self):
        if not all(isinstance(v, str) and 0 < len(v) <= 200 for v in (self.peer, self.conversation)):
            raise BriefingRefused("conversation_identity_required")


@dataclass(frozen=True)
class Work:
    text: str
    request_id: str
    revision: int
    session_id: str | None
    replaces: tuple[str, ...] | None = None
    inputs: dict | None = None


@dataclass(frozen=True)
class Answer:
    turn: TurnResult
    # Component identifiers and DataRefs originate in validated local handlers,
    # never in the specialist's output text.
    cards: dict[str, DataRef]
    required_components: tuple[str, ...] = ("flight_status", "weather_hourly", "arrival_timeline")
    inputs: dict | None = None


Runner = Callable[[Work], Awaitable[Answer]]


@dataclass
class _Job:
    owner: Owner
    text: str
    revision: int = 1
    request_id: str = field(default_factory=lambda: uuid4().hex)
    session_id: str | None = None
    status: str = "started"
    reason: str | None = None
    progress: list[str] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)
    turn: TurnResult | None = None
    task: asyncio.Task | None = None
    board: WidgetBoard = field(default_factory=WidgetBoard)
    inputs: dict | None = None
    needs_input: dict | None = None
    replaces: tuple[str, ...] | None = None


class Jobs:
    """In-memory, bounded session demo; shutdown cancels all outstanding jobs."""

    def __init__(self, runner: Runner, *, timeout: float = 60, capacity: int = 128,
                 replacement_plan: Callable[[str], tuple[str, ...] | None] | None = None,
                 ownership_mode: str = "engine"):
        if timeout <= 0 or capacity <= 0:
            raise ValueError("Positive job limits required")
        self._runner, self._timeout, self._capacity = runner, timeout, capacity
        self._jobs: dict[str, _Job] = {}
        self._replacement_plan = replacement_plan
        if ownership_mode not in ("engine", "capability"):
            raise ValueError("unsupported_ownership_mode")
        self.ownership_mode = ownership_mode
        install_log_redaction()

    @staticmethod
    def _snapshot(job: _Job) -> list[dict]:
        cards = []
        for state in job.board.snapshot():
            if state.replaced:
                # Core pending CardState revision is zero, not a valid
                # widget.upsert. Publish only supersession metadata, no old
                # numeric values masquerading as current data.
                cards.append({"replaced": True, "widget_id": state.widget_id,
                              "component": state.component, "request_id": state.request_id,
                              "revision": state.revision})
                continue
            event = WidgetUpsert(type="widget.upsert", request_id=state.request_id,
                                 widget_id=state.widget_id, component=state.component,
                                 data_ref=state.data_ref.id, revision=state.revision)
            cards.append({"event": event.model_dump(), "data_ref": state.data_ref.model_dump(),
                          "replaced": state.replaced})
        return cards

    @staticmethod
    def _text(value: str | None) -> str:
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise BriefingRefused("invalid_request_text")
        return value.strip()

    def _owned(self, owner: Owner, job_id: str | None) -> _Job:
        job = self._jobs.get(job_id) if isinstance(job_id, str) else None
        if job is None or job.owner != owner:
            # Same response for unknown and another conversation's job.
            raise BriefingRefused("job_unavailable")
        return job

    async def from_transport(self, authenticated_peer: str | None, metadata: dict | None,
                             **arguments) -> dict:
        """Private transport entry; only arguments is the public tool payload."""
        if self.ownership_mode == "capability":
            if not authenticated_peer:
                raise BriefingRefused("authenticated_peer_required")
            # This is explicitly capability possession, not sender binding.
            owner = Owner(authenticated_peer, "capability-possession")
        else:
            owner = Owner(*conversation_identity(authenticated_peer, metadata))
        return await self.briefing(owner, **arguments)

    async def briefing(self, owner: Owner, *, action: str, request: str | None = None,
                       job_id: str | None = None, change: str | None = None) -> dict:
        if not isinstance(owner, Owner):
            raise BriefingRefused("conversation_identity_required")
        if action == "start" and request is not None and job_id is None and change is None:
            text = self._text(request)
            if len(self._jobs) >= self._capacity:
                raise BriefingRefused("job_capacity_reached")
            # 32 random bytes = 256 random bits; UUID4 would supply only122.
            job_id = "brf_" + secrets.token_urlsafe(32)
            job = _Job(owner, text)
            job.board.begin_request(job.request_id)
            self._jobs[job_id] = job
            job.task = asyncio.create_task(self._run(job, job.request_id))
            return {"job_id": job_id, "status": "started"}
        if action == "get" and job_id is not None and request is None and change is None:
            job = self._owned(owner, job_id)
            result = {"status": job.status, "progress": list(job.progress),
                      "widgets": [c["event"]["widget_id"] for c in job.cards if not c["replaced"]],
                      "cards": deepcopy(job.cards), "revision": job.revision,
                      "request_id": job.request_id}
            if job.needs_input is not None:
                result["needs_input"] = deepcopy(job.needs_input)
            if job.reason is not None:
                result["reason"] = job.reason
            return result
        if action == "revise" and job_id is not None and change is not None and request is None:
            job = self._owned(owner, job_id)
            update = self._text(change)
            targets = self._replacement_plan(update) if self._replacement_plan else None
            if targets is not None:
                known = {state.widget_id for state in job.board.snapshot()}
                if not targets or len(set(targets)) != len(targets) or not set(targets) <= known:
                    raise BriefingRefused("invalid_replacement_targets")
            if job.task is not None:
                job.task.cancel()
            # Rotate identity before spawning; even an uncancellable old worker
            # cannot publish into the replacement generation.
            job.request_id = uuid4().hex
            if targets is None:
                job.board.begin_request(job.request_id)
            else:
                job.board.begin_request(job.request_id, replaces=list(targets))
            job.replaces = targets
            job.revision += 1
            job.text = update
            job.status, job.reason = "started", None
            job.needs_input = None
            job.cards = self._snapshot(job)
            job.progress = ["Selected cards superseded; refreshing"]
            job.task = asyncio.create_task(self._run(job, job.request_id))
            return {"job_id": job_id, "status": "started", "revision": job.revision}
        raise BriefingRefused("invalid_action_arguments")

    async def _run(self, job: _Job, request_id: str) -> None:
        work = Work(job.text, request_id, job.revision, job.session_id, job.replaces, deepcopy(job.inputs))
        job.status = "running"
        job.progress.append("Checking sources")
        try:
            answer = await asyncio.wait_for(self._runner(work), self._timeout)
            if job.request_id != request_id:
                return
            if answer.inputs is not None:
                job.inputs = deepcopy(answer.inputs)
            job.turn = answer.turn
            job.session_id = answer.turn.session_id
            for component, reference in answer.cards.items():
                reference.check(component)
                event = WidgetUpsert(type="widget.upsert", request_id=request_id,
                                     widget_id=component.replace("_", "-"), component=component,
                                     data_ref=reference.id, revision=work.revision)
                job.board.apply(event, reference)
                # Report completed validation stages, not imagined provider work.
                job.progress.append({"flight_status": "flight", "weather_hourly": "weather",
                                     "arrival_timeline": "timeline", "market_watchlist": "market"}[component])
            job.cards = self._snapshot(job)
            required = set(answer.required_components)
            available = {state.component for state in job.board.snapshot()
                         if not state.replaced and state.data_ref.error is None}
            if answer.turn.ok and required <= available and answer.turn.calls:
                job.status = "complete"
                job.progress.append("Validated source cards ready")
            else:
                job.status, job.reason = "incomplete", "required_sources_or_completed_tool_turn_missing"
        except NeedsInput as missing:
            if job.request_id == request_id:
                job.status, job.reason = "needs_input", None
                job.inputs = deepcopy(missing.inputs)
                job.needs_input = {"field": missing.field, "question": missing.question}
                job.progress.append("Waiting for traveller input")
                job.cards = self._snapshot(job)
        except asyncio.CancelledError:
            # Cancellation does not authorize cancelling the remote managed turn;
            # old results remain fenced by request identity.
            return
        except TimeoutError:
            if job.request_id == request_id:
                job.status, job.reason = "incomplete", "briefing_timeout"
                job.cards = self._snapshot(job)
        except Exception:
            if job.request_id == request_id:
                job.status, job.reason = "failed", "briefing_unavailable"
                job.cards = self._snapshot(job)

    async def close(self) -> None:
        tasks = [job.task for job in self._jobs.values() if job.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
