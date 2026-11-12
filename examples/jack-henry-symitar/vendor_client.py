# SPDX-License-Identifier: MIT
"""Private async vendor client, not a model tool or an authorization boundary.

The trusted adapter supplies vendor identifiers. The host must authorize both
accounts, consume consent and durably journal before calling postTransfer.
This client has no default transport, credentials, network setup or retries.
Validated vendor data is private and must be minimized by the adapter.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import json
import re
from typing import Protocol

from contract_inputs import ContractError, OPERATIONS, SymitarContract

MAX_BODY = 1_048_576


class ErrorCode(str, Enum):
    INVALID_REQUEST = "invalid_request"
    INVALID_RESPONSE = "invalid_response"
    VENDOR_REJECTED = "vendor_rejected"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


class ClientError(Exception):
    def __init__(self, code: ErrorCode):
        self.code = code
        super().__init__(code.value)


@dataclass(frozen=True)
class WireRequest:
    method: str
    path: str = field(repr=False)
    body: bytes = field(repr=False)
    media_type: str = "application/json"


@dataclass(frozen=True)
class WireResponse:
    status: int
    media_type: str
    body: bytes = field(repr=False)


@dataclass(frozen=True)
class VendorResult:
    """Schema-valid private payload, NOT a claim of business success/posting."""
    operation_id: str
    status: int
    data: object = field(repr=False)


class AsyncTransport(Protocol):
    async def send(self, request: WireRequest) -> WireResponse: ...


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def _reject_constant(value):
    raise ValueError("nonfinite_json")


class SymitarClient:
    def __init__(self, transport: AsyncTransport, contract: SymitarContract,
                 institution_id: str):
        if not isinstance(institution_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", institution_id):
            raise ClientError(ErrorCode.INVALID_REQUEST)
        self._transport = transport
        self._contract = contract
        self._institution = institution_id

    async def call(self, operation_id: str, request_body: object) -> VendorResult:
        try:
            if not isinstance(operation_id, str) or operation_id not in OPERATIONS:
                raise ValueError("unsupported_operation")
            # Serialize before awaiting: mutation by a caller cannot change the
            # validated request between this validation and physical dispatch.
            raw = json.dumps(request_body, allow_nan=False, separators=(",", ":")).encode()
            if len(raw) > MAX_BODY:
                raise ValueError("oversize_request")
            body = json.loads(raw)
            template = self._contract.request(operation_id, body)
            path = template.replace("{InstitutionUniversalId}", self._institution)
            request = WireRequest("POST", path, raw)
        except Exception:
            raise ClientError(ErrorCode.INVALID_REQUEST) from None
        try:
            response = await self._transport.send(request)  # Exactly one attempt.
        except Exception:
            code = ErrorCode.UNKNOWN if operation_id == "postTransfer" else ErrorCode.UNAVAILABLE
            raise ClientError(code) from None
        try:
            if not isinstance(response, WireResponse) or type(response.status) is not int:
                raise ValueError("invalid_response")
            if not isinstance(response.body, bytes) or len(response.body) > MAX_BODY:
                raise ValueError("oversize_response")
            media = response.media_type.split(";", 1)[0].strip().lower()
            data = json.loads(response.body, object_pairs_hook=_unique_object,
                              parse_constant=_reject_constant)
            self._contract.response(operation_id, response.status, media, data)
        except Exception:
            code = ErrorCode.UNKNOWN if operation_id == "postTransfer" else ErrorCode.INVALID_RESPONSE
            raise ClientError(code) from None
        if response.status != 200:
            # A server failure can follow an effect; never call it a failed transfer.
            code = (ErrorCode.UNKNOWN if operation_id == "postTransfer" and response.status >= 500
                    else ErrorCode.VENDOR_REJECTED)
            raise ClientError(code)
        return VendorResult(operation_id, response.status, data)
