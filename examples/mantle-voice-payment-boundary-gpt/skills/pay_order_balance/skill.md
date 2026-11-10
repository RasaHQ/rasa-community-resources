---
name: Pay Order Balance
description: >
  Help a signed-in Willow Shop customer pay the balance on an order that is on
  hold, through a secure payment link by text or email. Activate for "I need
  to pay for my order", "my order is on hold for payment", "can I pay the
  balance", "can I give you my card number", "I already paid", and for
  questions about what is owed on an order.
tool_constraints:
  - send_secure_payment_link:
      requires: session.pay_order_balance.pay_order
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_payment_link
---

Card details are never taken on this call. Payment happens only on the
payment processor's secure page, sent as a link by text or email to the
contact details on the account.

1. If the caller starts reading a card number, an expiry date or a security
   code, or asks you to take their card, say plainly that you can't take card
   details on the call, ask them not to read any, and offer the secure link by
   text or email. Never repeat, confirm or write down any card digits, and
   never ask the caller to repeat them. What you see in their place is
   "[card details removed]".
2. Get the order number. Call @tool.look_up_order_balance if the caller asks
   what they owe; otherwise go straight on.
3. Ask whether they want the link by text or by email, only if they have not
   said. Then call @tool.prepare_secure_payment with the order and channel,
   and when it returns ready, call @tool.send_secure_payment_link with the
   same order straight away. Do not ask for confirmation yourself: the engine
   reads the order, amount and channel back and asks the caller.
4. If the caller answers the engine's question with a change (another order,
   email instead of text), decline the confirmation, call
   @tool.prepare_secure_payment for what they now want, and ask them to
   confirm again. The engine does not accept a second
   send_secure_payment_link in the same turn.
5. If the caller does not want the secure step at all, call
   @tool.leave_payment_pending. Nothing is charged and the order stays on
   hold.
6. When the caller says they have paid, call @tool.check_payment_status. Only
   a succeeded result means paid. A caller's confirmation number or word is
   not a receipt. If it returns expired, offer a new link and prepare it
   again.
7. When prepare_secure_payment returns blocked or cancelled, follow its
   next_step: take no card details, do not ask for any again, and give the
   approved alternative.
8. The tools tell the caller the outcome themselves: link sent, paid with the
   processor reference, not confirmed, or left unpaid. The caller has already
   heard it. Do not restate the processor reference, the order number or the
   amount after a tool has said them; add only what is still useful, in one
   short sentence, or ask if there is anything else.
