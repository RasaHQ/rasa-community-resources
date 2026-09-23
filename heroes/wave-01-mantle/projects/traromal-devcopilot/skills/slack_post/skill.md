---
name: slack_post
description: >
  Post, read, reply, or react in Slack. Activate when the developer clearly
  asks to use Slack, not when Slack is merely mentioned.
import_tools:
  - mcp/slack:post_message
  - mcp/slack:list_channels
  - mcp/slack:list_messages
  - mcp/slack:reply_in_thread
  - mcp/slack:add_reaction
tool_constraints:
  - post_message:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_slack_post
  - reply_in_thread:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_slack_reply
  - add_reaction:
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_slack_reaction
---

Help the developer work with Slack safely.

For a post, use the remembered preferred_slack_channel when available,
otherwise default to all-devcopilot. Call list_channels to confirm the
channel, summarize the exact message, and then call post_message after the
confirmation gate.

For a thread reply, collect the channel, thread timestamp or message context,
and exact reply before calling reply_in_thread.

For a reaction, collect the channel, message timestamp, and emoji before
calling add_reaction.

For reading, call list_messages and summarize without posting anything.

If a write returns ok true, say what changed and name the channel. If it
returns an error, say it could not be completed and give the reason briefly.

Keep the reply to one short spoken sentence.
