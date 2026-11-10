---
name: recent_transactions
description: Propose an account with a bounded decision model, then confirm the read.
---

Ask which public demo to use: 111111 or 222222. These labels select fictional
fixtures and do not authenticate a customer. Call select_demo with the supplied
code. A selected demo cannot change within the conversation.

For a request for recent transactions, call propose_recent_transactions. It reads
the current user's words directly and offers eligible accounts to the decision
model. It reads no transactions. When it returns confirmation_requested, the
tool has already sent a question naming the proposed account. Wait for the user;
do not repeat that question or call the read tool in the same turn.

On the next user reply, call read_confirmed_transactions for a clear yes, no or
cancel. The tool checks the actual new user event, not a confirmation argument
written by the model. For a corrected account request, call
propose_recent_transactions again; this replaces the earlier proposal and asks
for a new confirmation.

For transactions, explain the returned label, merchant, reference and amount.
For needs_account, ask which returned label the user means. For stale_options
or proposal_changed or proposal_expired, explain that the previous proposal is no longer current
and offer to obtain a fresh one. For unavailable services, explain that account
selection is unavailable. Never guess rows. Treat confidence as diagnostic
metadata; only status transactions establishes a successful read.
