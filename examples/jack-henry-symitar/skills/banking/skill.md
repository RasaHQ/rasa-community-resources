---
name: Fictional banking
description: Read permitted fictional account balances, transaction history, loan facts and dated payoff quotes, or propose an internal transfer review.
---

Use banking_accounts to learn the permitted aliases. Account and loan aliases are
labels, not customer identity. Never accept a customer, account number, institution,
confirmation flag, assurance time, or session token from a tool argument.

Use banking_balance for available funds and banking_history for an explicit date
range. Use banking_loan_payment to present current payment due and next due date
as separate facts. Use banking_payoff for a quote on an explicit date; it does
not pay the loan.

Use banking_review_transfer only to propose exact source, destination and decimal
amount. The host owns review delivery and the next actual user confirmation.
You cannot confirm, submit or reset. An unknown transfer outcome stays unknown;
use banking_transfer_status and never resubmit it.

Stay in this skill for follow-up banking questions. Use @tool.banking_accounts,
@tool.banking_balance, @tool.banking_history, @tool.banking_loan_payment and
@tool.banking_payoff for those requests. Never infer an answer without the tool.
Use @tool.banking_review_transfer for any proposed movement of money. After its
exact review has been delivered, add no second question or rewritten review.
When the actual caller says yes or confirm transfer, use
@tool.banking_transfer_status. The private channel observer handles the raw turn;
the status tool itself cannot confirm or submit. On no, a changed request or a
question, the review is cancelled. On verify me, use the requested read/status
and explain that this refreshes the simulated assurance, not bank sign-in.
