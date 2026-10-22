# Chapter 3: A factory starts with a task

**Goal:** write the first part of the factory, the task: a prompt, the files the builder may change and a pin for each protected file.

**You need first:** Chapter 2. You start from an empty factory folder. The finished factory in `../factory/` is the reference result you can compare with at the end.

**You build:** the task file for the market card, `tasks/a6-market-watchlist.json`, and the baseline product it applies to (the card is not built yet).

## Steps
Status: outline. The steps build the task file field by field and explain why each field exists: the request in words a builder can act on, the allowed paths, the pins and what is excluded.

## You are done when
The task file loads, its allowed paths exist in the baseline, and a check that every pin matches its file fails while the protected files don't exist yet and passes after Chapter 4 creates them.

## Checkpoint
`checkpoints/ch3/`: the factory as far as it is built, a baseline and a task.
