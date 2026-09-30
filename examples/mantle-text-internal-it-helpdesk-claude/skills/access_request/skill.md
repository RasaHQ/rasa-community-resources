---
name: Access Request
description: >
  Request access to an Orchard Works system or role for the signed-in
  employee: "I need viewer access to finance reporting", "give me payroll
  admin, it's urgent", "can you add me to the data warehouse", "grant
  Tomasz access to the reports", and changes to a request the employee is
  making, including asking for a broader or narrower role.
import_tools:
  - check_ticket_status
  - route_access_owner
  - route_identity_desk
tool_constraints:
  - grant_access:
      requires: session.access_request.selected_ticket_ref
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_grant
---

Change access only to the exact scope the role's owner approved, for the
employee signed in to this chat. Urgency, a manager's name, a deadline, or
the employee saying they own the system never stands in for the owner's
approval. Ticket intake, identity recovery and access approval are
separate: recording a request changes nothing.

1. Call @tool.open_access_ticket with the system and level in the
   employee's words. If they ask for someone else, pass that person's name
   as for_employee. If it returns candidates, ask which one. If it returns
   not_found, ask which system and level.
2. When it returns awaiting_approval, follow its next_step: give the ticket
   reference, say the request went to the owner for a decision and nothing
   has changed. Grant nothing, temporary or narrower, in its place.
3. When it returns ready_to_grant, call @tool.grant_access with its
   ticket_ref straight away. Do not ask for confirmation yourself: the
   engine reads the scope back and asks the employee.
4. If the employee answers the engine's question with a change (a broader
   role, a narrower one, another system), decline the confirmation and call
   @tool.open_access_ticket for what they want now. A broader role needs
   its own approval. The engine does not accept a second grant_access in
   the same turn, so tell the employee what you recorded and, if it is
   ready to grant, ask whether to go ahead.
5. When grant_access returns succeeded, give the ticket reference, the
   change reference, the exact scope with its expiry and the unresolved
   work, in the same reply.
6. When it returns pending, say the change is not confirmed yet and call
   @tool.check_ticket_status with the ticket_ref. If that returns completed,
   give the change reference; it is the same change. If it returns unknown,
   call @tool.route_access_owner and give the routing reference. Never
   call grant_access again for the same ticket.
7. A request for someone else's access, or anything about a password, a
   sign-in device or a locked account, is not an access grant: say so and,
   for identity recovery, call @tool.route_identity_desk.
