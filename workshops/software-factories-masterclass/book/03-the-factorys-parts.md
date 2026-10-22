# Chapter 3: The factory's parts

**Goal:** learn the five parts of the factory loop (the task, the protected acceptance, the isolated change, the independent check and the decision) by running them on a small example.

**You need first:** Chapter 0. The factory runs offline and needs no model call.

**You build:** nothing new. You run the existing factory on good and bad candidates and read why each is accepted or rejected.

## Steps
Status: outline. The steps run `factory.py` in `../factory/` on the card-blocking task: one good candidate and the bad ones, then read each record.

## You are done when
`factory.py` ACCEPTs the good candidate (exit 0) and REJECTs the bad ones (exit 1), and you can name the check that rejected each.

## Checkpoint
`checkpoints/ch3/`.
