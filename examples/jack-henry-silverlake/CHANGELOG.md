# Changelog

Newest first. "Vendor files" entries record what changed in Jack Henry's jXchange archive and whether this example was affected. "Example changes" entries record changes to this example itself. File hashes are in [VENDOR-FILES.md](VENDOR-FILES.md).

## Vendor files

- 12 Nov 2026: first version used, the TPG R2026.1.00 XSD archive as published 3 Nov 2026. No change since.

## Example changes

- 13 Nov 2026: a different Jack Henry archive starts the example when everything it uses still fits, and it says so; otherwise it stops and names the operation. Added this changelog and the version table.
- 13 Nov 2026 (#225): every "yes" or "confirm" is answered by the host: it sends only an armed review after the exact words "confirm transfer"; otherwise it says the review was cancelled, or that an earlier outcome is unknown and must not be retried, including after a restart or when the status cannot be read. A transfer review the model types itself becomes the real review call. A question about another person's account no longer stalls.
- 12 Nov 2026 (#220): the assistant knows the account names from the start and does not repeat itself. Only the host speaks a transfer review or "accepted". "Verify me" is answered only when the host refreshes verification from that turn, including as the very first message. After a review is cancelled or interrupted, nothing accepts it.
- 12 Nov 2026 (#216): the walkthrough explains each step and its limits.
