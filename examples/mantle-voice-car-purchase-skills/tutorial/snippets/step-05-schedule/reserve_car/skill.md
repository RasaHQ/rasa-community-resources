---
name: Reserve Car
description: >
  Place a hold on a specific car at a specific Rasa Motors dealer. Activate when
  the customer wants to reserve, hold, put aside, or claim a vehicle, or book a
  car for a test drive.
import_tools:
  - load_customer_profile
  - check_availability
  - finalize_reservation
tool_constraints:
  - finalize_reservation:
      requires: session.reserve_car.selected_model and session.reserve_car.selected_dealer and session.reserve_car.reservation_confirmed
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_reserve
        utter_on_user_denial: utter_reserve_cancelled
      on_success: utter_reserved
utter:
  - utter_recording_notice:
      on: activate
  - utter_finance_notice:
      when: session.reserve_car.payment_method == "finance"
---

Help the customer reserve a car. Never reserve a car you have not confirmed is
in stock, and never invent a price or a dealer.

If username is missing, call `@tool.load_customer_profile`.

## Why they want the car

Ask what the hold is for. Valid reasons: test_drive, purchase_intent, hold.
Set `reservation_reason` via `set_fields`. One short question is enough.

Once the reason is collected, invoke `@block.pick_vehicle`

:::ordered_block id=pick_vehicle
steps:
  - id: name_the_car
    instructions: |
      Ask which car they want held. Set requested_model to what they say.
      If they already named a car earlier in the conversation, set it without
      asking again.
    complete_when: session.reserve_car.requested_model
  - id: confirm_stock
    execute_tool: check_availability
    parameters:
      model: session.reserve_car.requested_model
  - id: select_vehicle
    instructions: |
      Use only the listings from the tool result. Read out at most two of them
      with the model, the price, and the dealer. Ask which one they want held.
      Set selected_model to the exact model string, selected_dealer to that
      dealer, and selected_price to that price.
      If nothing came back, say it is not in stock and stop — do not invent one.
    complete_when: session.reserve_car.selected_model and session.reserve_car.selected_dealer
:::

## How they plan to pay

Ask whether they are paying cash or financing. Set `payment_method`.

if: session.reserve_car.payment_method == "cash"
Say cash buyers usually complete in a single dealer visit. Do not quote any
interest figures.

if: session.reserve_car.payment_method == "finance"
Say you can work out monthly payments once the car is held, and that terms of
36, 48, and 60 months are available. Do not quote a rate here — offer to run
the numbers with the financing skill afterwards.

## Confirm and reserve

Read the model, the price, and the dealer back in one short sentence. When the
customer agrees, set `reservation_confirmed` to true and call
`@tool.finalize_reservation` with the selected model, dealer, and price.

Give them the reservation reference and say the car is held for three days.

if: session.reserve_car.reserved == True
Offer to book a dealer appointment or to work out the monthly payment.
