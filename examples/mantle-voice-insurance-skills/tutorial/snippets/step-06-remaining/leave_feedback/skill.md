---
name: Leave Feedback
description: >
  Collect a quick thumbs-up or thumbs-down rating after the conversation.
  Activate when the customer wants to leave feedback or after goodbye.
---

Ask for a quick rating. Set `feedback_rating` to thumbs_up or thumbs_down.

if: session.leave_feedback.feedback_rating == "thumbs_up"
Thank them warmly in one short sentence.

if: session.leave_feedback.feedback_rating == "thumbs_down"
Apologize briefly and thank them for the feedback in one short sentence.
