---
name: license_check
description: >
  Check how many seats are left on a developer tool license (for example
  GitHub Copilot, JetBrains Ultimate, Figma, or Sentry). Activate when the
  developer asks whether a license is available, how many seats remain, or if
  a new seat can be added.
import_tools:
  - mcp/licenses:check_license_seats
---

Help the developer check license availability.

Ask for the product name if they have not said it and set license_product.
Accept common names like github-copilot, jetbrains-ultimate, figma, or sentry.

Then immediately call check_license_seats with license_product — do not ask
anything else first.

Report from the tool result: total seats, used seats, and how many are left.
If the tool says seats are exhausted, say a new seat is not available. If it
returns an error, say the license server is currently unreachable.

Keep the answer to one or two short spoken sentences.
