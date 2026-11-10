# Fixture data — entirely fictional

Every person, company, account, and event in this directory is **invented for
this project**. Nothing corresponds to a real person, a real business, or any
real conversation. Do not replace these records with real customer data — the
repo-wide `fictional-data` lint rejects real institutions and unreserved email
domains, and this catalog is public.

## SIM swap fixtures

`mobile_lines.json`, `registered_devices.json` and `sim_swaps.json` back the
`sim_swap` skill. The 555-01xx numbers sit in the range reserved for fiction,
and the device ids and swap references are made up. `DEV-123-01` is the one
device registered before any call, so it is the only valid app-push
destination. `DEV-123-02` is `pending` and stands in for a device enrolled
during the call. Customer `124` has a line but no registered device, which
exercises the handoff path. Customer `125`'s only device, `DEV-125-01`, is
active but was registered at 2026-09-21T10:04:00Z. The tests start the call
at 10:00 that day, so this device was enrolled during the call and is refused.
In a live session the call starts later than that fixture time, so the same
device would count. The tests pin the call start for that reason. `SWP-1001` is a finished swap stored as `active`,
so `check_swap_status` can be shown reading the stored status rather than
guessing it.
