# Fixture data (entirely fictional)

Amber Grid, its customers, accounts, balances, usage estimates and budget-plan
options are invented for this project. Nothing here corresponds to a real
energy supplier, person or account. Do not replace these records with real
customer data; this catalog is public.

- `amber_grid_budget.json`: the synthetic billing service. Each account has
  an outstanding balance and a budget quote: the usage estimate a budget
  amount is based on (`basis`) and the options the billing service authorizes
  at each quote revision. `AG-6121` (home gas) is re-estimated once, right
  after the first option is selected in a conversation: an actual meter
  reading replaces the estimated reads, so revision 1 is withdrawn and
  revision 2 carries new amounts. `AG-6125` (studio electricity) records a
  request but its read-back is delayed (`record_read_back: delayed`), so the
  first result is pending. `unauthorized_options` holds one option the
  billing service never authorized (`BP-6120-W`, the balance written off), and
  `AG-6388` belongs to another customer.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/utilities-budget-plan.json`, the
  lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

`lib/budget.py` refuses to load a fixture whose organisation is anything but
the contract's own fictional supplier, marked fictional. These files live
under `lib/` because Mantle packages `lib/` into the model snapshot and the
tools read them at runtime; a `data/` folder is not packaged.
