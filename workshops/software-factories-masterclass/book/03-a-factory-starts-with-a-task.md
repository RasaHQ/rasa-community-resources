# Chapter 3: A factory starts with a task

**Goal:** write the first part of the factory, the task: a prompt, the files the builder may change and a pin for each protected file.

**You need first:** Chapter 2. You start from an empty factory folder. The finished factory in `../factory/` is the reference result you can compare with at the end.

**You build:** the task file for the market card, `tasks/a6-market-watchlist.json`, and the baseline product it applies to (the card is not built yet). The pins stay empty for now.

## Steps
Status: outline. The steps build the task file field by field and explain why each field exists: the request in words a builder can act on, the allowed paths, the pins and what is excluded.

## You are done when
The task file loads as JSON with its request, its allowed paths and its excluded list, and every allowed path exists in the baseline. At the start checkpoint, before you write the task, that check fails. Pinning the protected files comes in Chapter 4, once they exist.

## Checkpoint
`checkpoints/ch3/`: the factory as far as it is built, a baseline and a task.
