---
name: Check Tickets
description: >
  Tell the caller what support tickets are on their account. Activate for open
  tickets, case status, or what is happening with my issue.
---

Report the caller's tickets.

Call `list_open_tickets`. It reads the identified customer from project memory,
so it is the authority on whether the caller has been identified yet.

- `not_identified`: say you need their email address first and let the Identify
  Customer skill run. Do not list anything.
- Success with `count` of zero: tell them there is nothing open.
- Success with tickets: read back each subject and its stage in plain language.
  `waiting_on_us` means Meridian owes them a reply; `waiting_on_contact` means
  the ticket is waiting on the customer.
- Any other error: say you could not reach the CRM. Never describe a ticket that
  did not come back from the tool.
