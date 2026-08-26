---
name: Reboot Router
description: >
  Guide the customer through power-cycling their router and confirm when they
  are done. Activate for reboot, restart router, or turn the router off and on.
---

Help the customer reboot their router. A reboot does not erase Wi-Fi settings.

Explain that they should turn the router off, wait about thirty seconds, then
turn it back on. Prefer the power button or unplugging the power cable.

Ask them to say when they are done. Set `reboot_done` to true when they confirm
success, or false if they report a problem.

if: session.reboot_router.reboot_done == True
Acknowledge the reboot and say you can run diagnostics again if needed.

if: session.reboot_router.reboot_done == False
Apologize briefly and offer to connect them to a human specialist.
