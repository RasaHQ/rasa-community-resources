---
name: Identify Customer
description: >
  Find the caller in the CRM from their email address. Activate when they give
  an email, introduce themselves, or when another skill needs an identified
  customer and there is not one yet.
import_tools:
  - find_contact_by_email
---

Identify the caller.

If they have already given an email address in what they just said, call
`find_contact_by_email` with it straight away. Do not ask them to repeat it.
Otherwise ask for the email address on their account, once, then call the tool.

Read the result before replying:

- Success: greet them by the returned name, mention their company, and ask what
  they need. Do not read the contact id aloud.
- `contact_not_found`: the CRM answered and nobody matches. Say you cannot find
  that address and ask them to check it or try another one.
- `crm_auth_failed`, `crm_timeout`, `crm_unreachable`, `crm_rate_limited`,
  `crm_not_configured`: you could not reach the CRM. Say so plainly and offer to
  take a message. Never guess who they are, and never continue as if they were
  identified.
