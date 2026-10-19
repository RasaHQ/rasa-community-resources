"""Consumer of the trusted producer's private pipe, never a command tool.

The authenticated host supplies a qualified interpreter, launcher and isolated
environment. No application, device, path or argument comes from a model.
This client does not load an SDK, obtain credentials, or repeat a discovery GET.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
from contextlib import suppress
import json
import os
from pathlib import Path
import re
import selectors
import signal
import subprocess
import threading
import time

from .budget import TurnBudget, current_budget
from .mantle_adapter import RetainedRead, TURN_BUDGET_SECONDS
from .turns import MAX_BYTES, TurnView

OPERATION = "zeoconnect.connections.list"
WORKER_TURN_BUDGET_SECONDS = min(7, TURN_BUDGET_SECONDS)  # Leave cleanup below tool_timeout=10.
MAX_REPLY = 4 * ((MAX_BYTES + 2) // 3) + 1024
_ENV = {"HOME", "TMPDIR", "XDG_CONFIG_HOME", "XDG_CACHE_HOME", "XDG_DATA_HOME",
        "XDG_STATE_HOME", "LANG", "LC_ALL", "TZ"}


class WorkerCleanupError(RuntimeError):
    """Host-only unresolved lifecycle evidence; never a successful cleanup receipt."""

    def __init__(self, process, failure):
        super().__init__("worker_cleanup_unavailable")
        self.owned_process = process
        self.failure = failure
        self.startup_error: BaseException | None = None


class ConversationBudget:
    """Keep this host-owned object across worker replacement; no reset on failure."""

    def __init__(self):
        self._lock = threading.Lock()
        self._attempts = 0
        self._used: set[str] = set()

    def attempt(self):
        with self._lock:
            if self._attempts >= 8:
                raise ValueError("conversation_exhausted")
            self._attempts += 1

    def bind(self, invocation):
        with self._lock:
            if not isinstance(invocation, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,256}", invocation):
                raise ValueError("invalid_invocation")
            if invocation in self._used:
                raise ValueError("invocation_reused")
            self._used.add(invocation)


def _object(pairs):
    if len({key for key, _ in pairs}) != len(pairs):
        raise ValueError("duplicate_reply_key")
    return dict(pairs)


class WorkerClient:
    """One serialized pipe/session; any invalid exchange permanently closes it."""

    def __init__(self, python: Path, launcher: Path, *, environment: dict[str, str],
                 conversation: ConversationBudget, startup_timeout: float = 2):
        if not python.is_absolute() or not launcher.is_absolute():
            raise ValueError("absolute owned interpreter and launcher required")
        if set(environment) - _ENV or not {"HOME", "TMPDIR"} <= set(environment):
            raise ValueError("isolated environment required")
        if not 0 < startup_timeout <= 5:
            raise ValueError("invalid startup timeout")
        self._conversation = conversation
        self._exchange_lock = threading.Lock()
        self._close_lock = threading.Lock()
        self._closed = False
        self.cleanup_state = "NOT_REQUESTED"
        self.cleanup_error: WorkerCleanupError | None = None
        self._requests = 0
        self._active: TurnBudget | None = None
        self._show_lock = asyncio.Lock()
        self._process = subprocess.Popen(
            (str(python), "-I", str(launcher)), stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=dict(environment),
            start_new_session=True, bufsize=0,
        )
        try:
            os.set_blocking(self._process.stdin.fileno(), False)
            os.set_blocking(self._process.stdout.fileno(), False)
            ready = self._line(TurnBudget(time.monotonic() + startup_timeout))
            if ready != {"ok": True, "outcome": "ready", "protocol": "zeoconnect.poc-worker/v1"} or type(ready.get("ok")) is not bool:
                raise ValueError("worker_not_ready")
        except BaseException as startup_error:
            try:
                self.close()
            except WorkerCleanupError as failure:
                failure.startup_error = startup_error
                raise
            raise

    def close(self):
        # Do not poll/reap before signalling the owned group: its leader PID
        # must remain reserved until all descendants have been signalled.
        with self._close_lock:
            if self._closed:
                if self.cleanup_error is not None:
                    raise self.cleanup_error
                return
            self._closed = True
            if self._active is not None:
                self._active.cancelled.set()
            try:
                try:
                    os.killpg(self._process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                except PermissionError as denied:
                    self.cleanup_state = "UNKNOWN_SIGNAL_PERMISSION_DENIED"
                    self.cleanup_error = WorkerCleanupError(self._process, denied)
                    # Do not try terminate/kill, another signal, another actor,
                    # or infer that failure to signal means the process exited.
                    raise self.cleanup_error from denied
                try:
                    self._process.wait(timeout=1)
                except subprocess.TimeoutExpired as timeout:
                    self.cleanup_state = "UNKNOWN_REAP_TIMEOUT"
                    self.cleanup_error = WorkerCleanupError(self._process, timeout)
                    raise self.cleanup_error from timeout
                self.cleanup_state = "DIRECT_CHILD_REAPED"
            finally:
                # Closing our pipe ends is containment, not proof of quiescence.
                for pipe in (self._process.stdin, self._process.stdout):
                    with suppress(OSError):
                        pipe.close()

    def _line(self, budget):
        raw = bytearray()
        with selectors.DefaultSelector() as selector:
            selector.register(self._process.stdout, selectors.EVENT_READ)
            while True:
                left = budget.remaining()
                if self._closed:
                    raise ValueError("worker_closed")
                for key, _ in selector.select(min(left, 0.05)):
                    chunk = os.read(key.fd, min(4096, MAX_REPLY + 1 - len(raw)))
                    if not chunk:
                        raise ValueError("worker_eof")
                    raw.extend(chunk)
                    if len(raw) > MAX_REPLY:
                        raise ValueError("worker_reply_bound")
                    if b"\n" in raw:
                        if not raw.endswith(b"\n") or raw.count(b"\n") != 1 or raw.startswith(b"\xef\xbb\xbf"):
                            raise ValueError("worker_reply_framing")
                        result = json.loads(raw.decode("utf-8"), object_pairs_hook=_object,
                                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("invalid_number")))
                        if not isinstance(result, dict):
                            raise ValueError("worker_reply_object")
                        return result

    def _exchange(self, request, expected, budget):
        # The turn owner serializes calls; a failed request is never retried.
        if not self._exchange_lock.acquire(blocking=False):
            self.close()
            raise ValueError("concurrent_worker_exchange")
        try:
            budget.remaining()
            if self._closed or self._requests >= 32:
                raise ValueError("worker_unavailable")
            self._requests += 1
            pending = memoryview(json.dumps(request, separators=(",", ":")).encode() + b"\n")
            if len(pending) > 1024:
                raise ValueError("worker_request_bound")
            with selectors.DefaultSelector() as selector:
                selector.register(self._process.stdin, selectors.EVENT_WRITE)
                while pending:
                    for key, _ in selector.select(min(budget.remaining(), 0.05)):
                        written = os.write(key.fd, pending)
                        pending = pending[written:]
            result = self._line(budget)
            if set(result) != {"ok", "outcome", *expected} or result.get("ok") is not True or result.get("outcome") != "completed":
                raise ValueError("worker_refused_or_invalid")
            budget.remaining()
            return result
        except BaseException:
            self.close()
            raise
        finally:
            self._exchange_lock.release()

    def _begin(self, budget):
        self._conversation.attempt()
        value = self._exchange({"method": "begin"}, {"operation", "invocation"}, budget)
        if value["operation"] != OPERATION:
            raise ValueError("worker_operation")
        self._conversation.bind(value["invocation"])
        return value["invocation"]

    def _read(self, invocation, budget):
        value = self._exchange({"method": "read", "invocation": invocation},
                               {"operation", "invocation", "envelope_base64"}, budget)
        if value["operation"] != OPERATION or value["invocation"] != invocation:
            raise ValueError("worker_result_binding")
        encoded = value["envelope_base64"]
        if not isinstance(encoded, str) or len(encoded) > 4 * ((MAX_BYTES + 2) // 3):
            raise ValueError("worker_envelope_bound")
        try:
            raw = base64.b64decode(encoded, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError("worker_envelope_invalid") from None
        if len(raw) > MAX_BYTES:
            raise ValueError("worker_envelope_bound")
        return RetainedRead(OPERATION, invocation, raw)

    def _contains(self, operation, invocation, budget):
        value = self._exchange({"method": "contains", "operation": operation,
                                "invocation": invocation}, {"retained"}, budget)
        if type(value["retained"]) is not bool:
            raise ValueError("worker_retention_type")
        return value["retained"]

    async def show(self, view: TurnView) -> dict[str, str]:
        # Queueing a second tool call must not extend its deadline or resurrect
        # a previous turn. The authenticated host serializes conversation turns.
        if self._show_lock.locked():
            self.close()
            return {"status": "unavailable"}
        async with self._show_lock:
            budget = TurnBudget(time.monotonic() + WORKER_TURN_BUDGET_SECONDS)
            self._active = budget
            token = current_budget.set(budget)
            turn = view.begin(OPERATION, "")
            budget.valid = lambda: view.is_current(turn)
            validation_done = threading.Event()
            validation_started = threading.Event()
            try:
                def accept(result):
                    validation_started.set()
                    try:
                        return view.accept(
                            turn, result.envelope,
                            retained_original=lambda op, inv: self._contains(op, inv, budget),
                        )
                    finally:
                        validation_done.set()

                async def complete():
                    nonlocal turn
                    invocation = await asyncio.to_thread(self._begin, budget)
                    reserved = view.bind(turn, OPERATION, invocation)
                    if reserved is None:
                        raise ValueError("superseded_turn")
                    turn = reserved
                    result = await asyncio.to_thread(self._read, invocation, budget)
                    return await asyncio.to_thread(accept, result)
                accepted = await asyncio.wait_for(complete(), timeout=budget.remaining())
                if accepted:
                    budget.remaining()
                if not accepted:
                    self.close()
                return {"status": "displayed" if accepted else "unavailable"}
            except BaseException as error:
                budget.cancelled.set()
                view.fail(turn)
                cleanup_error = None
                try:
                    self.close()
                except WorkerCleanupError as failure:
                    cleanup_error = failure
                if validation_started.is_set():
                    # CoreProcess polls this same budget and reaps its child in
                    # finally. A custom validator must honor the same contract.
                    await asyncio.to_thread(validation_done.wait, 1.25)
                if isinstance(error, asyncio.CancelledError):
                    raise
                if cleanup_error is not None:
                    if cleanup_error is error:
                        raise
                    raise cleanup_error from error
                if not isinstance(error, Exception):
                    raise
                return {"status": "unavailable"}
            finally:
                current_budget.reset(token)
                self._active = None
