---
name: docs_lookup
description: >
  Search the web for current documentation, guides, or how-to articles.
  Activate when the developer asks what the latest docs say, how to do
  something in a framework or tool, whether a feature exists in a given
  version, or requests any factual reference that is not covered by the
  internal safety FAQ. Do not activate for internal project questions
  such as tickets, deployments, licenses, or Slack — those have their
  own skills.
import_tools:
  - mcp/exa:web_search_exa
  - mcp/exa:web_fetch_exa
---

Help the developer find current documentation or how-to references.

Start with web_search_exa. Prefer results from official documentation
sites (for example docs.rasa.com, stackoverflow.com, or the official
docs of the tool the developer named). Summarise the answer in one or
two short spoken sentences and cite the page title or URL.

Only call web_fetch_exa when the search snippet does not contain enough
detail to answer the question. If web_search_exa returns no useful
results, say so clearly and offer to escalate to the on-call engineer.

Keep the reply short enough to speak aloud. Never read out full code
blocks — describe what the docs say instead.
