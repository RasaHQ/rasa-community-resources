---
name: Enquiry Status
description: >
  Status of an enquiry the applicant already recorded, by its support
  reference. Activate for "what happened to my enquiry PU-SUP-40A1C2", "did
  anyone reply to my question", "check my support reference".
import_tools:
  - check_enquiry
  - route_to_team
---

Call @tool.check_enquiry with the support reference the applicant gives. If
they have none, ask for it; it is on the message they were sent when the
enquiry was recorded. Report the enquiry's state, team and application
exactly as the result gives them. An open enquiry is not a decision on the
application. If the result is unknown, say no enquiry with that reference is
on their record.
