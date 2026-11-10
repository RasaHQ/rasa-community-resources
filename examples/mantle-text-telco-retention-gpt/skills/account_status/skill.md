---
name: Account Status
description: >
  Read one of the signed-in customer's services and end retention contact.
  Activate for "what am I paying for my mobile", "is my cancellation request
  open", "has my offer been applied", "stop sending me offers", "stop
  texting me about deals", "unsubscribe me".
import_tools:
  - get_account_status
  - withdraw_contact
---

Call @tool.get_account_status with the service the customer names. Their
services are @memory.project.service_list. Report exactly what it returns.

When the customer says to stop contacting them, stop the offer messages or
unsubscribe, call @tool.withdraw_contact. The customer has then refused
offers: make none, for the rest of the conversation. Never offer anything
from here; for a cancellation, use the cancel-or-stay skill.
