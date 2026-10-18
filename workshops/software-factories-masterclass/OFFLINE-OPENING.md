# Offline opening: the 14:30 and 14:40 blocks without profrod.ai

The first two blocks of `FACILITATOR.md` point to profrod.ai, which needs a network. This page replaces them when the room has none, or when you would rather not depend on it. Everything here runs from this repository after `uv sync --frozen`. Nothing runs against a live model.

## 14:30 A grader the builder cannot edit is the only review a dark factory has (10 min)

Say, in your words:

- A coding agent changes a project. Something has to decide whether the change is acceptable. In a factory that runs without a person reading every change, that decision is the only review.
- If the builder can edit the check, a pass proves nothing. So the check lives where the builder's workspace cannot write.
- A pass rate from a few runs is a count with an error bar. Show it:

      python measure.py intervals 4

  The row `4  1.00 to 1.00  0.51 to 1.00` is four passes in four runs: the simple interval says 1.00 to 1.00, the Wilson interval says 0.51 to 1.00. Four clean runs do not show a high pass rate.
- Say that nothing today runs against a live model.

Participants: with their partner, answer "Who can edit the check in your team's agent workflow today?" No answer is collected.

## 14:40 A forged pass fools the first factory and is rejected by the second (20 min)

The pack's own factory is the toy. Run from `factory/`:

    python factory.py tasks/a1-block-card.json candidates/block-card-good runs/toy-good
    # ACCEPT - protected acceptance passed

    python factory.py tasks/a1-block-card.json candidates/block-card-tamper runs/toy-tamper
    # REJECT - files outside the allowed paths: acceptance/a1_block_card.py

    python factory.py tasks/a1-block-card.json candidates/block-card-forges-accept runs/toy-forge-1
    # ACCEPT - protected acceptance passed          (the first factory is fooled)

    python factory_v2.py tasks/a1-block-card.json candidates/block-card-forges-accept runs/toy-forge-2
    # REJECT - the protected acceptance suite failed: exited with status 0 without unittest's OK line and a test count

Say: the third candidate ends the process early with status 0 and the first factory takes that for a pass. The second factory requires the test runner's own closing lines. A grader is code too, and it has to be graded.

Run folder names must be new each time: the factory refuses to reuse one. This is the pack's analogue of profrod.ai Lessons 1 and 2, not a copy of them.
