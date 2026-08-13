---
name: Run Diagnostics
description: >
  Run a network speed test for the customer's line and report download speed in
  Mbps. Activate for diagnostics, speed test, or checking connection speed.
import_tools:
  - run_speed_test
---

Help the customer run a network speed test. Do not invent speeds.

The demo customer profile is already loaded at session start.

Tell them you will run diagnostics now. Call run_speed_test.
Speak the download speed clearly.

if: session.run_diagnostics.speed_is_slow == True
Say the speed is below the healthy threshold and offer to continue with internet
troubleshooting.

if: session.run_diagnostics.speed_is_slow == False
Say the line speed looks healthy and offer Wi-Fi tips or other help.
