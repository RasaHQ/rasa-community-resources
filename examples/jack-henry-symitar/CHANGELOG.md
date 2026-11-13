# Changelog

Newest first. "Vendor files" entries record what changed in Jack Henry's API definitions and whether this example was affected. "Example changes" entries record changes to this example itself. File hashes are in [VENDOR-FILES.md](VENDOR-FILES.md).

## Vendor files

### 13 Nov 2026: files as published 12 Nov 2026, 22:38 UTC

- accounts.yaml, transactions.yaml and loans.yaml changed; transfers.yaml did not.
- accounts.yaml: the optional request filter `memberNumber` (one string) became `memberNumbers` (a list of strings) in the two account lookups. It narrows a reply to the shares and loans a member is related to.
- All three: a `404` (not found) reply is now documented on their operations.
- Effect on this example: none. It never sends that filter and reads only successful replies. What we changed: new hashes, and a start-up check so that newer files which change nothing this example uses no longer stop it.

### 12 Nov 2026: accounts as published 12 Nov 2026, 19:31 UTC

- accounts.yaml changed: a new optional request field, `memberNumber`, in the two account lookups.
- Effect on this example: none, as it does not send the field. What we changed: the new hash (#222).

## Example changes

- 13 Nov 2026: newer Jack Henry files start the example when nothing it uses has changed, and it says so; otherwise it stops and names the change. Added this changelog and the version table.
- 13 Nov 2026 (#223): only the host speaks a transfer review or "accepted"; model text that imitates one is replaced by a line that claims nothing. A transfer review the model types itself becomes the real review call. "Verify me" is answered only when the host refreshes verification from that turn, including as the very first message. The assistant knows the account names from the start and does not repeat itself. After a review is cancelled or interrupted, "yes" never accepts and a new request is needed. An unknown transfer outcome is never retried. A status question hears the outcome from the host.
- 12 Nov 2026 (#222): pinned the republished accounts.yaml.
- 12 Nov 2026 (#216): the walkthrough explains each step and its limits.
