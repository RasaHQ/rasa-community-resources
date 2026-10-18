# Participant pre-work: draft message for the operator to send

DRAFT, not sent. This pack does not message participants. The operator decides whether, when and how to send it, and who the participants are.

---

Subject: Before Thursday 22 October: 15 minutes, once, on the laptop you will bring

Please do this once before the session, with a normal internet connection. It downloads about 750 MB. In the room we will not do it.

1. Install `git` and `uv` if you do not have them, and use Python 3.11 or newer.
2. Clone the repository: `git clone https://github.com/RasaHQ/rasa-community-resources` and note the commit shown by `git log -1`. [Operator: replace with the exact commit participants should use.]
3. In `workshops/software-factories-masterclass/factory`, run `uv sync --frozen`.
4. Run `uv run python factory.py tasks/a1-block-card.json candidates/block-card-good runs/check`. You should see `ACCEPT - protected acceptance passed`.
5. If step 4 does not print ACCEPT, bring the laptop anyway and tell us what it printed. We will pair you with someone.

A copy of the environment made on another computer may not work on yours: it is tied to the operating system and Python version. Please run the commands yourself.

---

Notes for the operator:

- A pre-synced folder on a USB drive is a fallback only. It is tied to the operating system of the machine that made it, and has not been tested on a second machine.
- `factory/rehearse.py` runs every command of the session in order, offline, and prints the time and result of each block. Run it on the machine you will present from.
