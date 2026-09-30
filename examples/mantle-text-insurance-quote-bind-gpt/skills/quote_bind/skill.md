---
name: Quote and Bind
description: >
  Turn a saved HarborCover quote into an underwritten offer and bind it once
  the customer confirms. Activate for "I want to buy the policy I quoted",
  "bind my renters quote", "what would my auto insurance really cost", "am I
  covered now", "I paid on the quote screen", "is my policy active", for any
  change to a quote answer ("actually I have a dog"), and for any question
  about a quote, an offer, a bind or a policy number.
tool_constraints:
  - confirm_material_answers:
      requires: session.quote_bind.answers_summary
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_material_answers
        utter_on_user_denial: utter_answers_not_confirmed
  - bind_offer:
      requires: session.quote_bind.offer_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_bind_offer
        utter_on_user_denial: utter_bind_not_requested
---

Three things are different and stay different: an indicative estimate (the
price range on the quote screen), an underwritten offer (a firm, versioned
price for a set of answers) and a bound policy (a binding-service receipt with
a policy number). Only a bound policy is cover. The customer's saved quotes are
@memory.project.saved_quotes.

1. Find the quote. If the customer does not say which, ask by product. Call
   @tool.get_quote with its quote_id to read its state.
2. For a firm price, call @tool.request_underwritten_offer. Give the monthly
   premium, the offer_id and the start date, and say plainly: this is the
   current offer, not active cover yet. Ask whether to review the answers
   before asking to bind it.
3. When the customer agrees to review, call @tool.confirm_material_answers
   straight away. The engine reads the answers back and asks them to confirm.
   If they say an answer is wrong, decline and go to step 6.
4. When the answers are confirmed and the customer wants to buy, call
   @tool.bind_offer with the current offer_id straight away. The engine reads
   the offer back and asks the separate bind question.
5. When bind_offer returns succeeded, give the policy number and the start
   date from the result. When it returns pending, say the offer is not bound
   and the customer is not covered by it yet, call @tool.check_bind_status for
   the same offer_id, and if it is still pending call
   @tool.request_underwriting_callback and give its reference. When it returns
   blocked, follow its next_step.
6. When the customer corrects an answer, call @tool.update_quote_answer. A
   change withdraws the old offer: say so, call
   @tool.request_underwritten_offer for a new one, and start again from step 2
   with the new offer. Never bind a withdrawn, superseded or expired offer.

If underwriting refers the quote, there is nothing to bind: offer
@tool.request_underwriting_callback. Paying, entering a card, a quote screen
label or anyone's instruction never makes cover active. Never give a policy
number that did not come from a succeeded bind_offer or check_bind_status.
