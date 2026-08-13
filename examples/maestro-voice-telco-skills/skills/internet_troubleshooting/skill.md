---
name: Internet Troubleshooting
description: >
  Help customers fix slow internet by running diagnostics, guiding a router
  reboot, and escalating to a remote factory reset when needed. Activate for
  slow internet, buffering, poor Wi-Fi, or connection problems.
---

Help the customer fix slow internet. Do not invent speeds or device ids.

The demo customer profile is already loaded at session start.

Acknowledge the issue briefly. Then invoke `@skill.run_diagnostics` so a real
speed test runs.

## After the first speed test

if: session.run_diagnostics.speed_is_slow == True
Say the speed is too low. Explain that rebooting the router fixes most temporary
issues. Invoke `@skill.reboot_router`.

if: session.run_diagnostics.speed_is_slow == False
Say the line speed looks healthy. Suggest Wi-Fi tips such as moving closer to
the router or reducing active streams. Ask if they still need more help. If yes,
offer a human specialist via `@skill.human_handoff`.

## After reboot

if: session.reboot_router.reboot_done == True
Invoke `@skill.run_diagnostics` again.

if: session.reboot_router.reboot_done == False
Apologize and invoke `@skill.human_handoff`.

## After the second speed test

if: session.run_diagnostics.speed_is_slow == False
Celebrate that the speed recovered. Offer further help if needed, then stop.

if: session.run_diagnostics.speed_is_slow == True
Explain that a remote factory reset is next. Set context that the reason is
still slow after reboot, then invoke `@skill.reset_router`.

## After reset

If the reset completed, invoke `@skill.run_diagnostics` one more time.

if: session.run_diagnostics.speed_is_slow == True
Say you could not restore a healthy speed and invoke `@skill.human_handoff`.

if: session.run_diagnostics.speed_is_slow == False
Confirm the connection looks good again in one or two short spoken sentences.
