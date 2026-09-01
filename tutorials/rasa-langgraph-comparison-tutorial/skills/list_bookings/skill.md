---
name: List Bookings
description: >
  Show the traveller which flights they currently have booked. Activate for
  my flights, my bookings, what have I booked, or show my itinerary.
import_tools:
  - list_flight_bookings
---

Show the traveller their flights.

The lookup is an ordered block rather than an instruction to call a tool. Asked
in prose, the model will sometimes answer from the error cases listed below
instead of calling anything — which is how you end up reporting an outage that
never happened.

:::ordered_block id=show
steps:
  - id: fetch
    execute_tool: list_flight_bookings
  - id: report
    instructions: |
      Report what the tool returned, and only that.

      With flights: list each as flight number, route and departure time, one
      line each. Do not read out ticket numbers or flight ids unless asked.

      With `count` of zero: say they have no flights booked.

      With an error: say plainly that you could not read their bookings. Never
      describe a flight that did not come back from the tool.
:::
