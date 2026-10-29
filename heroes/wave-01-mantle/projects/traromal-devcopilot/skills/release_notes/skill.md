---
name: release_notes
description: >
  Draft release notes for a project from its pull requests and deployments.
  Activate when they ask for release notes, a changelog draft, or a ship
  summary.
---

Collect the project name if needed. Call draft_release_notes.

Return a short draft containing the project, latest deployment information,
pull-request titles, CI warnings, and any open critical tickets that should
be mentioned before release.

This skill only drafts text. It must not deploy, post to Slack, or modify a
ticket unless the developer explicitly starts another skill for that action.
