# SPDX-License-Identifier: MIT
"""Own local fictional core, built from manually supplied pinned OpenAPI.

No vendor definition or generated schema is bundled. Required response shapes
are generated in memory from verified definitions; only authored fictional data
is overlaid. Every request and response crosses the existing contract validator.
There is no bank URL, credential or network fallback. A successful fixture
transfer changes local state, not money. Host consent is a separate boundary.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date
from decimal import Decimal
import fcntl
from http.server import BaseHTTPRequestHandler, HTTPServer
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import threading

import yaml

from contract_inputs import ContractError, OPERATIONS, SymitarContract, load_inputs
import demo_data
import vendor_api
from vendor_client import MAX_BODY, WireRequest, WireResponse, _unique_object, _reject_constant

FIXTURE = demo_data.FIXTURE


class MockRefused(Exception):
    """Redacted fixture failure, never a claim of a real vendor's decision."""


def _schema(schema, document):
    for _ in range(32):
        if "$ref" not in schema:
            return schema
        reference = schema["$ref"]
        if not reference.startswith("#/"):
            raise MockRefused("nonlocal_fixture_reference")
        schema = document
        for part in reference[2:].split("/"):
            schema = schema[part.replace("~1", "/").replace("~0", "~")]
    raise MockRefused("recursive_fixture_reference")


def _required(schema, document, depth=0):
    """Generate a minimal synthetic shape at runtime, never vendor examples."""
    if depth > 24:
        raise MockRefused("fixture_shape_limit")
    schema = _schema(schema, document)
    if "enum" in schema:
        return deepcopy(schema["enum"][0])
    if schema.get("nullable"):
        return None
    if "allOf" in schema:
        result = {}
        for item in schema["allOf"]:
            result.update(_required(item, document, depth + 1))
        return result
    if "anyOf" in schema or "oneOf" in schema:
        return _required(schema.get("anyOf", schema.get("oneOf"))[0], document, depth + 1)
    kind = schema.get("type", "object")
    if kind == "object":
        return {key: _required(schema["properties"][key], document, depth + 1)
                for key in schema.get("required", [])}
    if kind == "array":
        count = schema.get("minItems", 0)
        if count > 32:
            raise MockRefused("fixture_shape_limit")
        return [_required(schema["items"], document, depth + 1) for _ in range(count)]
    if kind in {"integer", "number"}:
        return schema.get("minimum", 0)
    if kind == "boolean":
        return False
    if kind == "string":
        return {"date": "2026-11-12", "date-time": "2026-11-12T12:00:00Z",
                "uuid": "00000000-0000-4000-8000-000000000001"}.get(schema.get("format"), "0")
    raise MockRefused("unsupported_fixture_shape")


class FixtureState:
    """Private local SQLite state, with a lifetime OS writer lease.

    Initialization is explicit and refuses an existing database. Recovery never
    reseeds, unlinks or clears state. The future stopped-fixture reset command
    must preserve old epochs and audit before deliberately initializing another.

    The demo data seed is chosen once, when the state is initialized, and is
    stored with it; ``seed`` is ignored when reopening. Seed 0 is the reference
    data. Every reopen checks the stored fingerprint against
    ``demo_data.data_hash(stored_seed)``. A database from before seeds existed
    has no seed column and is treated as seed 0 with the same file check.
    """
    def __init__(self, path: Path, epoch: str, *, initialize=False, seed=demo_data.REFERENCE_SEED):
        self._connection = None
        self._lease = None
        self._mutex = threading.RLock()
        self.seed = None
        path = Path(path).absolute()
        if path != path.resolve() or not re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", epoch):
            raise MockRefused("invalid_fixture_location_or_epoch")
        if type(seed) is not int or not 0 <= seed <= demo_data.MAX_SEED:
            raise MockRefused("invalid_fixture_seed")
        try:
            if initialize:
                # Preserve partially initialized files on failure; never reseed.
                descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
                os.close(descriptor)
                self._lease = os.open(str(path) + ".lease", os.O_CREAT | os.O_EXCL | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            else:
                if not path.is_file() or path.is_symlink():
                    raise MockRefused("fixture_state_missing")
                self._lease = os.open(str(path) + ".lease", os.O_RDWR | os.O_NOFOLLOW)
            fcntl.flock(self._lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._connection = sqlite3.connect(path.as_uri() + "?mode=rw", uri=True, check_same_thread=False)
            self._connection.execute("PRAGMA synchronous=FULL")
            self._connection.execute("PRAGMA busy_timeout=1000")
            if initialize:
                fixture = demo_data.generate(seed)
                self._connection.execute("CREATE TABLE fixture (id INTEGER PRIMARY KEY CHECK(id=1), epoch TEXT NOT NULL, seed_hash TEXT NOT NULL, data TEXT NOT NULL, sends INTEGER NOT NULL, seed INTEGER NOT NULL)")
                self._connection.execute("INSERT INTO fixture VALUES (1,?,?,?,0,?)", (epoch, demo_data.data_hash(seed), json.dumps(fixture), seed))
                self._connection.commit()
                for folder in (path.parent,):
                    descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
                    try:
                        os.fsync(descriptor)
                    finally:
                        os.close(descriptor)
            columns = {item[1] for item in self._connection.execute("PRAGMA table_info(fixture)")}
            seed_column = "seed" if "seed" in columns else str(demo_data.REFERENCE_SEED)
            row = self._connection.execute(f"SELECT epoch,seed_hash,data,sends,{seed_column} FROM fixture WHERE id=1").fetchone()
            if (row is None or row[0] != epoch or type(row[4]) is not int or not 0 <= row[4] <= demo_data.MAX_SEED
                    or (initialize and row[4] != seed) or row[1] != demo_data.data_hash(row[4])):
                raise MockRefused("fixture_epoch_or_seed_changed")
            json.loads(row[2])
            self.seed = row[4]
        except Exception:
            self.close()
            raise MockRefused("fixture_state_unavailable") from None

    def transact(self, operation):
        with self._mutex:
            try:
                self._connection.execute("BEGIN IMMEDIATE")
                raw, sends = self._connection.execute("SELECT data,sends FROM fixture WHERE id=1").fetchone()
                data = json.loads(raw)
                result, changed = operation(data)
                if changed:
                    self._connection.execute("UPDATE fixture SET data=?,sends=? WHERE id=1", (json.dumps(data), sends + 1))
                self._connection.commit()
                return result
            except Exception:
                self._connection.rollback()
                raise

    def snapshot(self):
        with self._mutex:
            raw, sends = self._connection.execute("SELECT data,sends FROM fixture WHERE id=1").fetchone()
            return json.loads(raw), sends

    def close(self):
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._lease is not None:
            os.close(self._lease)
            self._lease = None


class SymitarMock:
    def __init__(self, inputs, state: FixtureState):
        self.contract = SymitarContract(inputs)  # Hash/ref/type gate before YAML use.
        self.state = state
        self._responses = {}
        self._routes = {}
        fixture, _ = state.snapshot()
        self._institution = fixture["institution"]
        for raw in inputs.values():
            document = yaml.safe_load(raw)
            for path, methods in document["paths"].items():
                for method, operation in methods.items():
                    if method != "post" or not isinstance(operation, dict) or operation.get("operationId") not in OPERATIONS:
                        continue
                    name = operation["operationId"]
                    route = path.replace("{InstitutionUniversalId}", self._institution)
                    self._routes[route] = name
                    self._responses[name] = (operation["responses"]["200"]["content"]["application/json"]["schema"], document)
        if set(self._responses) != OPERATIONS:
            raise MockRefused("fixture_operation_missing")

    @classmethod
    def from_directory(cls, state, directory=None):
        return cls(load_inputs(directory), state)

    def _shape(self, operation, *keys):
        schema, document = self._responses[operation]
        for key in keys:
            schema = _schema(schema, document)
            schema = schema["items"] if key == "[]" else schema["properties"][key]
        return _required(schema, document)

    def _response(self, operation, body, data):
        number = data["account_number"]
        if body.get("accountNumber") != number and operation != "postTransfer":
            raise MockRefused("unsupported_fixture_selector")
        if operation in {"findAccountBy", "findAccountByWithBalances"}:
            if set(body) != {"accountNumber"}:
                raise MockRefused("unsupported_fixture_selector")
            response = self._shape(operation)
            response["shares"] = []
            for share in data["shares"]:
                item = self._shape(operation, "shares", "[]")
                item.update(accountNumber=number, shareId=share["id"], nickname=share["alias"], accountStatus="Active")
                if operation == "findAccountByWithBalances":
                    item.update(balance=share["balance"], availableBalance=share["available"])
                response["shares"].append(item)
            # Loan output comes from the separate exact loans operation.
            return response, False
        if operation == "searchLoans":
            if set(body) - {"accountNumber", "loanId"}:
                raise MockRefused("unsupported_fixture_selector")
            response = []
            for loan in data["loans"]:
                if body.get("loanId", loan["id"]) != loan["id"]:
                    continue
                item = self._shape(operation, "[]")
                item.update(accountNumber=number, loanId=loan["id"], nickname=loan["alias"], accountStatus="Active",
                            balance=loan["balance"], paymentDue=loan["payment_due"], dueDate=loan["due_date"],
                            payment=loan["regular_payment"], minimumPayment=loan["minimum_payment"], pastDueAmount=loan["past_due"])
                response.append(item)
            return response, False
        if operation == "calculateLoanPayoffQuote":
            if set(body) != {"accountNumber", "loanId", "payoffDate"}:
                raise MockRefused("unsupported_fixture_selector")
            loan = next((item for item in data["loans"] if item["id"] == body["loanId"]), None)
            days = (date.fromisoformat(body["payoffDate"]) - date.fromisoformat(data["payoff"]["reference_date"])).days
            if loan is None or not 0 <= days <= data["payoff"]["max_days"]:
                raise MockRefused("unsupported_fixture_quote")
            amount = Decimal(loan["balance"]) + days * Decimal(data["payoff"]["daily_interest"])
            return {"totalPayoffAmount": format(amount, ".2f"), "payoffDate": body["payoffDate"], "loanEligible": True,
                    "maxDays": data["payoff"]["max_days"], "disclaimerText": ["Fictional fixture arithmetic; not a bank quote."]}, False
        if operation == "searchAccountTransactions":
            if set(body) - {"accountNumber", "shareId", "startDate", "endDate", "count", "offset"} or body.get("shareId") not in {share["id"] for share in data["shares"]}:
                raise MockRefused("unsupported_fixture_selector")
            start, end = date.fromisoformat(body["startDate"]), date.fromisoformat(body["endDate"])
            count, offset = body.get("count", 20), body.get("offset", "0")
            if start > end or type(count) is not int or not 1 <= count <= 20 or not re.fullmatch(r"[0-9]{1,6}", offset):
                raise MockRefused("unsupported_fixture_page")
            selected = [item for item in data["transactions"] if item["share_id"] == body["shareId"] and start.isoformat() <= item["date"] <= end.isoformat()]
            page = selected[int(offset):int(offset) + count]
            rows = []
            for item in page:
                row = self._shape(operation, "transactions", "[]")
                row.update(postDate=item["date"], description=item["description"], amount=item["amount"], sequenceNumber=item["sequence"])
                rows.append(row)
            next_offset = str(int(offset) + len(page)) if int(offset) + len(page) < len(selected) else ""
            return {"transactions": rows, "paging": {"nextOffset": next_offset, "results": len(rows), "total": len(selected)}}, False
        if operation == "postTransfer":
            if set(body) != {"donor", "recipient", "amount"} or not isinstance(body["amount"], str) or not re.fullmatch(r"(?:0|[1-9][0-9]{0,6})\.[0-9]{2}", body["amount"]):
                raise MockRefused("unsupported_fixture_transfer")
            selectors = [body["donor"], body["recipient"]]
            if any(set(item) != {"accountNumber", "shareId"} or item["accountNumber"] != number for item in selectors):
                raise MockRefused("unsupported_fixture_selector")
            shares = {item["id"]: item for item in data["shares"]}
            source, destination = [item["shareId"] for item in selectors]
            amount = Decimal(body["amount"])
            if source not in shares or destination not in shares or source == destination or amount <= 0 or amount > Decimal(shares[source]["available"]):
                raise MockRefused("unsupported_fixture_transfer")
            for key in ("balance", "available"):
                shares[source][key] = format(Decimal(shares[source][key]) - amount, ".2f")
                shares[destination][key] = format(Decimal(shares[destination][key]) + amount, ".2f")
            return {"status": "success", "confirmationNumber": None, "receiptId": None}, True
        raise MockRefused("unsupported_fixture_operation")

    def send(self, request: WireRequest) -> WireResponse:
        """Validate raw wire request and commit fixture effect before response."""
        try:
            if request.method != "POST" or request.media_type != "application/json" or type(request.body) is not bytes or len(request.body) > MAX_BODY:
                raise MockRefused("invalid_fixture_request")
            operation = self._routes[request.path]
            body = json.loads(request.body.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_reject_constant)
            self.contract.request(operation, body)
            def execute(data):
                response, changed = self._response(operation, body, data)
                # Built through the operation's generated model; a value that does not fit
                # fails here and the fixture change is rolled back.
                response = vendor_api.reply_body(operation, response)
                self.contract.response(operation, 200, "application/json", response)
                return WireResponse(200, "application/json", json.dumps(response, allow_nan=False).encode()), changed
            return self.state.transact(execute)
        except (MockRefused, ContractError, ValueError, KeyError, TypeError):
            # Authored Problem Details, never a bank rejection claim.
            return WireResponse(400, "application/problem+json", b'{"type":"urn:fictional:unsupported","title":"Fictional fixture request refused","details":[]}')
        except Exception:
            # A commit/I/O failure can follow an effect: the client must hold
            # transfer outcome unknown, not infer a definitive rejection.
            return WireResponse(500, "application/problem+json", b'{"type":"urn:fictional:unavailable","title":"Fictional fixture unavailable","details":[]}')


class DirectFixtureTransport:
    """Offline injectable transport; no network or retry."""
    def __init__(self, mock):
        self.mock = mock

    async def send(self, request):
        return self.mock.send(request)


def local_mock_server(mock: SymitarMock, bearer: str, port=0):
    """Real loopback vendor-wire boundary with a private host-injected bearer."""
    if not isinstance(bearer, str) or re.fullmatch(r"[A-Za-z0-9_-]{32,128}", bearer) is None:
        raise MockRefused("private_bearer_required")

    class Handler(BaseHTTPRequestHandler):
        timeout = 5

        def log_message(self, *args):
            pass

        def reply(self, response):
            self.send_response(response.status)
            self.send_header("Content-Type", response.media_type)
            self.send_header("Content-Length", str(len(response.body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Connection", "close")
            self.end_headers()
            self.wfile.write(response.body)
            self.close_connection = True

        def do_POST(self):
            auth = self.headers.get_all("Authorization")
            if self.headers.get_all("Origin") or self.headers.get_all("Host") != ["127.0.0.1:" + str(self.server.server_port)] or auth is None or len(auth) != 1 or not hmac.compare_digest(auth[0].encode(), ("Bearer " + bearer).encode()):
                self.reply(WireResponse(403, "application/json", b"{}"))
                return
            try:
                sizes = self.headers.get_all("Content-Length")
                if self.headers.get_all("Transfer-Encoding") or sizes is None or len(sizes) != 1 or re.fullmatch(r"[0-9]+", sizes[0]) is None or not 0 < int(sizes[0]) <= MAX_BODY:
                    raise ValueError("invalid_frame")
                raw = self.rfile.read(int(sizes[0]))
                if len(raw) != int(sizes[0]):
                    raise ValueError("short_frame")
                response = mock.send(WireRequest("POST", self.path, raw, self.headers.get_content_type()))
            except Exception:
                response = WireResponse(400, "application/json", b"{}")
            self.reply(response)

    return HTTPServer(("127.0.0.1", port), Handler)
