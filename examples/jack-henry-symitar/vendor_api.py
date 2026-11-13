# SPDX-License-Identifier: MIT
"""Which generated Symitar model belongs to each request and reply this example uses.

vendor_models/ is generated (make models); this small map is written by hand.
The models give the host typed request bodies and replies. They do not replace
the OpenAPI validators in contract_inputs.py, which stay the authority: every
request and reply is still validated against the pinned files on the wire.
"""
from __future__ import annotations

from pydantic import BaseModel

from vendor_models import accounts, loans, transactions, transfers

REQUEST: dict[str, type[BaseModel]] = {
    "findAccountBy": accounts.FindAccountByRequest,
    "findAccountByWithBalances": accounts.FindAccountByWithBalancesRequest,
    "searchAccountTransactions": transactions.SearchAccountTransactionsRequest,
    "searchLoans": loans.SearchLoansRequest,
    "calculateLoanPayoffQuote": loans.CalculateLoanPayoffQuoteRequest,
    "postTransfer": transfers.PostTransferRequest,
}
# The successful (200) reply of each operation.
REPLY: dict[str, type[BaseModel]] = {
    "findAccountBy": accounts.FindAccountByResponse,
    "findAccountByWithBalances": accounts.FindAccountByWithBalancesResponse,
    "searchAccountTransactions": transactions.SearchAccountTransactionsResponse,
    "searchLoans": loans.SearchLoansResponse,
    "calculateLoanPayoffQuote": loans.CalculateLoanPayoffQuoteResponse,
    "postTransfer": transfers.PostTransferResponse,
}
# The problem reply (400) a refused transfer carries.
PROBLEM: dict[str, type[BaseModel]] = {"postTransfer": transfers.PostTransferResponse1}


def request_body(operation: str, **fields) -> dict:
    """A request body built through its model: a missing required field or a wrong type fails here."""
    return REQUEST[operation].model_validate(fields).model_dump(mode="json", by_alias=True, exclude_unset=True)


def reply(operation: str, data) -> BaseModel:
    """The successful reply as its model."""
    return REPLY[operation].model_validate(data)
