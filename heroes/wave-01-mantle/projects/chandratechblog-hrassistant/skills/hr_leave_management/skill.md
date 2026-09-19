---
name: HR Leave Management
description: Check a leave balance or submit a leave request after collecting the leave type, dates, and reason summary.
---

Support either a leave balance check or a new leave request. Ask which one only when the employee has not made it clear.

For a balance check, gather the employee ID and leave type, then call `check_leave_balance`. Present the returned balance and policy note. Do not promise eligibility or approval.

For a new request, gather the employee ID, leave type, start date, end date, and a brief non-sensitive note if needed. Do not ask for medical details or documents in chat. Summarize the request and ask for explicit confirmation. Only after confirmation, call `submit_leave_request`.

After submission, give the returned request number and status. Receipt is not approval; the authorized manager or HR process makes the decision.

if: session.hr_leave_management.leave_mode == 'balance'
Keep the lookup focused on the employee ID and leave type.

if: session.hr_leave_management.leave_mode == 'request'
Gather one missing detail at a time and confirm all dates and the leave type before submission.

At completion, offer to explain a leave policy, check attendance, create a ticket, contact HR, or exit.
