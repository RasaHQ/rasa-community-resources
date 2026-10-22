# Chapter 6: The gates and the decision

**Goal:** build the part of the factory that judges a candidate: the gates in order and the recorded decision, then run it on good and bad candidates.

**You need first:** Chapters 4 and 5.

**You build:** the gate runner. It checks that the protected files still match their pins, that the candidate holds no copy of them and no symbolic link, that only the allowed paths changed, and that the protected suite passes. It then records the decision with its evidence and an exit code.

## Steps
Status: outline. The steps build each gate in turn and show a candidate that each one stops: a rate shown as live, an invented rate when the source fails and an edited protected suite.

## You are done when
The gate runner ACCEPTs the good candidate (exit 0) and REJECTs each bad one (exit 1), naming the check that stopped it, and it runs offline.

## Checkpoint
`checkpoints/ch6/`: the factory with a task, acceptance, a builder and gates.
