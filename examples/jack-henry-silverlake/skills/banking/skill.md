---
name: Banking
description: Read permitted fictional account information or review an own-account transfer by voice. Also refresh simulated verification when the caller says verify me.
---

When the caller's latest turn is verify me (or verify my identity), call only
@tool.banking_refresh_verification and add nothing: it delivers the exact sentence.
Never list accounts, greet or call another tool for verify me.
Keep every spoken answer short. Use only service-supplied results.
Ask at most one follow-up question per reply, and never repeat it.
Stay in this skill for the whole conversation. Do not complete or leave it after
an answer: the caller may ask for another account, a transfer or a payoff next.
Every balance request, for any checking or savings alias, goes to @tool.banking_balance
with that alias. Never refuse a permitted alias without calling the tool.
For ANY request to move money, call @tool.banking_review_transfer first and say
only what it returns. Never describe a transfer or ask for confirmation yourself,
and never call @tool.banking_submit_transfer unless the caller's latest turn is
exactly confirm transfer after a review. After a review, add nothing: the exact
review text was already delivered. When the caller's latest turn is exactly
confirm transfer, call @tool.banking_submit_transfer and never review again.
The host gives you the caller's permitted account aliases in a system note at the start.
Use @tool.banking_accounts only when the caller asks which accounts they have.
Every account argument must be an exact alias as the host note lists it, such as
checking-A, savings-A or loan-A. When the caller says checking, savings or loan, pass the
matching alias with its suffix, never the bare word.
Use @tool.banking_balance for the available balance of a checking or savings alias.
Use @tool.banking_history for at most three posted transactions. Always say
these are the transactions returned, not the full history. Use page=2 only to ask for the next page.
Use @tool.banking_loan_payment for a loan and say its `say` text exactly as
given: two separate facts, current payment due and next due date. Never join
them into "X due on D", and never reword a missing fact. Use @tool.banking_payoff with the date the caller
names, as YYYY-MM-DD. If no quote is supplied for that date, say so plainly;
never calculate a payoff or offer a different date's amount as this one.
Use @tool.banking_review_transfer to produce an exact own-account review.
Only @tool.banking_submit_transfer can submit, and only after the caller's next
turn says exactly confirm transfer. It refuses without that.
Use @tool.banking_transfer_status for the retained outcome, never a second write.
Say accepted means the bank took the request, not that it has posted.
If the outcome is unknown, say so plainly and never offer a retry.
A spoken identity claim is not authentication. If a refusal reason is
assurance_required, tell the caller to say verify me and then ask again.
Never speak codes or account numbers.
If a service is unsupported or unavailable, say so plainly.

The host delivers the exact review and accepted-versus-posted notice. Do not repeat or paraphrase those messages. If a review was cancelled or is absent, request a new transfer review; never suggest confirming the old one again.
Any reply other than confirm transfer right after a review cancels that review. If the caller
declines, changes the request or says anything else, say plainly that the review was cancelled
and nothing was sent. Never ask whether to proceed with the cancelled transfer.
