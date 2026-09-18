---
name: Who Handles This
description: >
  Say which department and named ward officer is responsible for a civic
  problem, and how long it usually takes. Activate whenever the caller asks
  who is responsible, who handles something, who to contact or complain to,
  which department or officer covers an area, or how long a problem normally
  takes — with or without naming a locality, and whether or not they go on to
  file anything. This is the only skill that can read the ward directory, so
  any question naming both a problem and a place belongs here.
---

:::ordered_block id=main
name: who_handles_this
description: Answer who is responsible, then offer to take the complaint.
steps:
  - id: answer
    instructions: |
      Call `who_handles` straight away, with whichever of the two you have —
      the kind of problem, the area, or both. You do not need both.

      Never answer this from your own knowledge. The ward directory is the
      only thing that knows who covers where, and it is not guessable.

      The tool speaks the answer itself. Add nothing to it.
    complete_when: session.who_handles_this.answered == True

  - id: offer
    instructions: |
      The answer has already been spoken. Do not repeat it, summarise it, or
      confirm it.

      Say one thing only: ask whether they would like to report it now. Set
      `report_now` to yes or no from their reply.
    complete_when: session.who_handles_this.report_now

  # A `call:` step, not an `@skill.` mention in the instructions above. Only
  # free prose is scanned for `@skill.` tokens — a reference written inside an
  # ordered-block step never compiles into referenced_skills, and the handoff
  # fails at runtime with "no such skill".
  - id: route
    noop: true
    next:
      - if: session.who_handles_this.report_now == "yes"
        then: take_the_complaint
      - then: sign_off

  - id: take_the_complaint
    call: report_problem

  - id: sign_off
    action: utter_nothing_filed
:::
