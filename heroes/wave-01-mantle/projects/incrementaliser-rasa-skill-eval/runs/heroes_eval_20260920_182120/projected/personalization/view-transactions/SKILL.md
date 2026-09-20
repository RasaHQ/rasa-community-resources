---
name: view-transactions
description: 'Show recent transactions for one of the customer''s accounts (checking
  or savings). Activate only when the customer clearly asks about spending history,
  recent charges, transactions, or statement activity.

  '
license: Apache-2.0
version: 0.1.0
compatibility: Rasa Mantle (rasa-pro 3.20.0.dev6)
metadata:
  author: RasaHQ <hi@rasa.com>
  version: 0.1.0
  rasa_skill_id: view_transactions
  rasa_display_name: View Transactions
---

# View Transactions

## Instructions

Help the customer review recent transactions on one account. Do not invent
merchants, amounts, dates, account ids, or transaction ids.

if: not session.view_transactions.selected_account_id and session.project.default_account_id
The customer has a usual account on file: @memory.project.default_account_label. Offer that one first by name — for example, "Want your usual @memory.project.default_account_label, @memory.project.customer_name?" If they say yes, set `selected_account_id` via `set_fields` to @memory.project.default_account_id. If they'd rather use a different account, or they already named one clearly (by name or last four), instead call `fetch_accounts`, present the accounts (name and last four digits), ask which one they want, and set `selected_account_id` via `set_fields` to the matching account id from the tool result. Do not invent accounts or set `selected_account_label`.

if: not session.view_transactions.selected_account_id and not session.project.default_account_id
Call `fetch_accounts` to load the customer's accounts. Present the accounts (name and last four digits) and ask which one they want recent transactions for. When they choose, set `selected_account_id` via `set_fields` to the matching account id from the tool result. If they already named one account clearly (by name or last four), set `selected_account_id` without re-asking. Do not invent accounts or set `selected_account_label`.

if: session.view_transactions.selected_account_id
Call `get_recent_transactions` for the selected account and present the returned
rows briefly (date, merchant, amount). If the tool returns no rows, say so
plainly. Answer any follow up questions regarding the transactions the user might have.

## Examples

- Customer: Show my recent transactions.
