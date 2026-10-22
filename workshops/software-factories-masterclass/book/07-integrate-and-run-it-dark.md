# Chapter 7: Integrate and run it dark

**Goal:** finish the factory with integration, then run the whole loop so the market card appears in your own agent without anyone reading the code.

**You need first:** Chapter 6.

**You build:** the integration step, which refuses a stale base and replays the earlier checks, and the run that takes the builder's change through the gates to ACCEPT and into the agent.

## Steps
Status: outline. The steps build integration, run the loop offline with a recorded builder and show the fourth card appear. A live builder on the OpenAI Agents API is the extra, with its spend limit and expected cost stated.

## You are done when
The offline run ends in ACCEPT and the market card shows in your running agent beside the other three.

## Checkpoint
`checkpoints/ch7/`: the finished factory.
