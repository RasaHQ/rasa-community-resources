---
name: Budget Plan
description: >
  Explain and request a budget plan on one of the signed-in customer's Amber
  Grid accounts, or refer them to the hardship team or billing support.
  Activate for "can I go on a budget plan", "even out my bills", "why is my
  budget amount so high", "what happens to what I owe", "can I spread my
  balance", "I can't afford my bill", "your colleague approved a plan", for
  any question about a budget estimate, a balance or a billing support option,
  and for changes to a budget plan choice.
tool_constraints:
  - request_budget_option:
      requires: session.budget_plan.option_tag
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_budget_option
---

A budget plan evens out payments for future usage. The monthly budget amount
is an estimate of that usage. It is a payment schedule, not a debt
adjustment: it never waives, reduces, replaces or absorbs the outstanding
balance. Only Amber Grid's billing service sets the options, and only the
hardship team decides any relief.

1. Work out which account. The customer's accounts are
   @memory.project.account_list. If more than one could fit, ask. Call
   @tool.get_budget_quote with the account.
2. Explain three things separately, from the result: the usage estimate the
   budget amount comes from, the outstanding balance and when it is due, and
   each option's schedule and balance handling exactly as given, with the
   option id. Say that no option reduces the balance. Then ask whether they
   would like to request one, review it, or speak to support. Never suggest,
   work out or promise any other amount, number of payments or date.
3. When the customer picks an option, call @tool.select_budget_option with
   its option_id, then call @tool.request_budget_option with the same
   option_id straight away. Do not ask for confirmation yourself: the engine
   reads the schedule, the estimate and the balance back and asks.
4. If the customer answers the engine's question with a change (another
   option or another account), decline the confirmation, call
   @tool.select_budget_option for the new choice and tell them its schedule
   and balance. The engine does not accept a second request_budget_option in
   the same turn; when they agree, call @tool.request_budget_option and the
   engine asks again.
5. If the customer says they cannot afford or cannot use the options, or asks
   for help paying, decline any pending confirmation and call
   @tool.route_hardship_referral with their words. It keeps the option they
   were considering with the referral. If they only ask for a different
   amount, say the billing service has not authorized one, show the
   authorized options again, and offer the hardship team if none is
   affordable. Never invent a cheaper plan and never say what the hardship
   team will decide.
6. If the customer wants to review an option with a person or speak to
   support, decline any pending confirmation and call
   @tool.route_billing_support.
7. When request_budget_option is blocked with unapproved_relief and a
   withdrawn_option, the estimate changed after the customer was asked: say
   the old schedule is withdrawn, present the current options exactly as
   given, and ask which they want. When blocked for an option the billing
   service never authorized, say so and present the authorized options.
8. When request_budget_option returns succeeded, the customer has already
   been sent the reference, the schedule and the balance. Add only what they
   still need. When it returns pending, say it is not recorded yet and call
   @tool.check_budget_request with the request_id. Never request the same
   option again.
9. A request that is already recorded cannot be changed here; for a change,
   call @tool.route_billing_support.
