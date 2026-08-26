---
name: Goodbye
description: >
  End the conversation politely when the customer says goodbye, thanks that's
  all, or wants to hang up. Optionally collect a quick thumbs-up or thumbs-down.
---

Thank the customer briefly.

If they seem done, you may ask for a quick thumbs up or thumbs down. Set
`feedback_rating` to thumbs_up or thumbs_down if they answer.

if: session.goodbye.feedback_rating == "thumbs_up"
Thank them for the positive feedback.

if: session.goodbye.feedback_rating == "thumbs_down"
Thank them and say you will use the feedback to improve.

Wish them a good day in one short spoken sentence and end the conversation.
