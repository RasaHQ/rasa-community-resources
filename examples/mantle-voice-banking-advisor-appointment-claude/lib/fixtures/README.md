# Fixture data (entirely fictional)

Northgate Bank, its Kingsmere, Farrowdale and Ashcombe branches, its teams,
the customer Eleanor Hartwell and every appointment slot are invented for
this project. Do not replace these records with real data; this catalog is
public. `lib/appointments.py` refuses to load a fixture whose organisation is
not exactly the casebook contract's organisation marked `(fictional)`. It
keeps no list of real names: the check is an allowlist.

- `appointments.json`: the synthetic advisor diary, on a fixed clock
  (`as_of`, Monday 5 October 2026 09:00 UK time). Eleanor, the signed-in
  customer, can book with these teams, each built to break one part of the
  case open:
  - Kingsmere branch (step-free): everyday banking only. A mortgage question
    there is the case's failure: no one at Kingsmere can handle it.
  - Farrowdale branch: everyday banking, and a mortgage advisor on Thursday
    at 2:30 pm. The branch is not step-free.
  - Ashcombe branch (step-free): everyday banking, a mortgage advisor on
    Friday at 10 am and an investment specialist on Wednesday at 3 pm.
  - The Northgate mortgage team (phone Thursday 2:30 pm and Friday 3 pm,
    video Wednesday 9:30 am), the investment specialists (video Thursday
    11 am and Friday 1:45 pm) and the business banking team (phone Tuesday
    noon and the following Monday 9 am). No mortgage slot falls on Tuesday.
  - Two slots misbehave on purpose. `SLT-KGM-0714` (Kingsmere, Wednesday
    2:30 pm) is taken by someone else between the proposal and the hold.
    The first hold on `SLT-INV-V0913` (video, Friday 1:45 pm) lapses before
    the booking goes through; a second hold works.
- `case-contract.json`: a copy of
  `tutorials/rasa-ai-team-casebook/examples/banking-advisor-appointment.json`,
  the lab contract whose three rules the tools enforce. `tests/test_guard.py`
  fails if the two copies drift apart.

These files live under `lib/` because Mantle packages `lib/` into the model
snapshot and the tools read them at import.
