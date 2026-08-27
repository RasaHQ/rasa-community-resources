---
name: Change Flight
description: >
  Move the traveller's existing booking to a different flight on the same route.
  Activate for change my flight, rebook, move my flight, or a different time.
import_tools:
  - list_flight_bookings
tool_constraints:
  - rebook_flight:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_rebook
        utter_on_user_denial: utter_rebook_cancelled
---

Move the traveller onto a different flight.

Rebooking is the one irreversible thing this agent does, so the sequence is an
ordered block rather than prose. Left to prose it works most of the time, which
is the problem: on some turns the model asks for a date instead of searching,
and the traveller is stuck in a conversation that never reaches a tool.

Note that every tool below is called by an `execute_tool` step, and none takes
arguments. Asking the model to call a tool from inside an `instructions` step is
where this skill kept failing — it would converse about the booking instead of
looking it up. And an `execute_tool` step stalls when the engine cannot fill a
parameter. An `execute_tool` step stalls when
the engine cannot fill a parameter — the model asks about the missing value
instead of running the step — so both tools read what they need from memory.

:::ordered_block id=rebook
steps:
  - id: fetch
    execute_tool: list_flight_bookings
  - id: pick_leg
    instructions: |
      From the flights the previous step returned, work out which one they want
      to change and set `current_flight_id` to its flight_id.

      If there is exactly one, use it without asking. If there are several, list
      them and ask which — then set the field from their answer.
    complete_when: session.change_flight.current_flight_id
  - id: search
    execute_tool: search_alternative_flights
  - id: choose
    instructions: |
      Present the options the search returned, numbered, as flight number and
      departure time. Present only what it returned.

      If `count` is zero, say there is nothing else on that route and stop.

      Ask which they want and set `selected_flight_id` to that option's
      flight_id. If they say "the next one" or "the first", take the earliest.
      Never offer the flight they already hold.
    complete_when: session.change_flight.selected_flight_id
  - id: apply
    execute_tool: rebook_flight
:::

## After the change

- Success: confirm briefly that the booking is moved.
- `not_your_ticket`, `flight_not_found`, `ticket_not_booked`: say the change did
  not go through and why. Never report a change the tool did not confirm.
