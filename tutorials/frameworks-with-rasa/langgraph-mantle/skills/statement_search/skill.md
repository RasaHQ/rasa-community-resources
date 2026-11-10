---
name: Statement Search
description: Help a user complete a paused synthetic statement lookup.
---

1. Explain that this is a synthetic demo. Ask for code 111111 or 222222. Wait for the user to provide it before calling @tool.select_demo. These codes do not authenticate a real customer.
2. When the user asks about travel spending, call @tool.start_statement_lookup once. It starts the existing LangGraph workflow and returns needs_month. Ask the returned question and wait for the user's reply. Do not call start_statement_lookup again merely because the user answered.
3. Convert an explicit month and year to YYYY-MM and call @tool.answer_statement_month. If the year is unclear, ask rather than inventing one. Invalid input does not consume the pause. The graph, not this conversation, performs the row lookup and total.
4. After complete, state the month, total in pounds and included row references. A lookup failure means no total is available; explain this and ask whether to retry or stop. Never claim a refused or incomplete call succeeded.
5. For a different month after completion, start a new lookup and then answer its month. The completed run stays associated with its original month; do not reinterpret its total. This does not move money or change any account.
