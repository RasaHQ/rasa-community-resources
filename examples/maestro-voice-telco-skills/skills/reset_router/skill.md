---
name: Reset Router
description: >
  Remotely factory-reset a customer router when a reboot did not fix persistent
  speed problems, or when the customer explicitly asks for a factory reset.
  Activate for factory reset, remote reset, wipe router settings, or reset after
  reboot failed.
import_tools:
  - run_speed_test
tool_constraints:
  - factory_reset_router:
      requires: session.reset_router.selected_device_id
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_reset_router
        utter_on_user_denial: utter_reset_cancelled
      on_success: utter_router_reset
  - run_speed_test:
      requires: session.reset_router.router_reset
utter:
  - utter_reset_warning:
      on: activate
  - utter_post_reboot_warning:
      when: session.reset_router.reset_reason == "still_slow_after_reboot"
---

Help the customer factory-reset a router. This is irreversible for custom
settings. Do not invent device ids.

The demo customer profile is already loaded at session start.

## Identify the reason

Ask why they need a factory reset. Valid reasons: still_slow_after_reboot,
wifi_broken, unknown_settings, moving, other. Set `reset_reason` via
`set_fields`.

Once the reason is collected, invoke `@block.pick_router`

:::ordered_block id=pick_router
steps:
  - id: fetch_routers
    execute_tool: list_routers
  - id: select_router
    instructions: |
      Show the customer's routers using model and device id from the tool result.
      Ask which router to reset. Set selected_device_id to the full device id and
      selected_device_label to the model name.
    complete_when: session.reset_router.selected_device_id
:::

## Handle reason

if: session.reset_router.reset_reason == "still_slow_after_reboot"
Explain that a factory reset is the next step after a reboot failed.
Call factory_reset_router with the selected device. Offer a post-reset speed test.

if: session.reset_router.reset_reason == "wifi_broken" or session.reset_router.reset_reason == "unknown_settings"
Explain that custom Wi-Fi settings will be wiped and restored to TelecomOfRasa-Setup.
Call factory_reset_router. Remind them to reconnect devices afterward.

if: session.reset_router.reset_reason == "moving" or session.reset_router.reset_reason == "other"
Confirm they understand settings will be erased, then call factory_reset_router.

## After reset

if: session.reset_router.router_reset == True
Offer to run diagnostics again. If they agree, call run_speed_test and
report the new speed in one or two short sentences.

## Close

Confirm what was done in one or two short sentences suitable for voice.
