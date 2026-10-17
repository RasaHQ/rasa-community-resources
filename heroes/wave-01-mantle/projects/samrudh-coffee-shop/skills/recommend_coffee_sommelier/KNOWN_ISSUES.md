# Known Issue: Multi-Turn Failure with Vertex AI / Gemini LLM Provider

### Summary
`recommend_coffee_sommelier` (and multi-tool skill workflows) executes successfully on the **first turn**. However, attempting a **second turn** within the same continuing conversation session fails when using the Google Vertex AI (`gemini/gemini-2.5-flash`) LLM provider via LiteLLM.

---

### Error Trace
```text
ProviderClientAPIException: litellm.BadRequestError: Vertex_ai_betaException BadRequestError - 
{
  "error": {
    "code": 400,
    "message": "Please ensure that function call turn comes immediately after a user turn or after a function response turn.",
    "status": "INVALID_ARGUMENT"
  }
}
```

---

### Why Turn 1 Succeeded but Turn 2 Failed

#### 1️⃣ Turn 1 (Fresh Session - Succeeds)
On the initial turn, conversation history is clean:
1. **User**: `"I want to place coffee order"`
2. **LLM**: Issues `tool_calls` (`place_coffee_order`)
3. **Tool**: Returns execution result (`{"ok": true, "order_id": "ORD-508"}`)
4. **LLM**: Summarizes output: `"Your order for Dark Roast Coffee is placed!"`

The sequence (`User ➔ Tool Call ➔ Tool Response ➔ Assistant Text`) completes cleanly.

---

#### 2️⃣ Turn 2 (Continuing Session - Fails with `400 INVALID_ARGUMENT`)
When the user sends a new message on Turn 2 (e.g. `"light works"`), Mantle passes the **entire accumulated conversation history** back to Google Gemini:

```python
[
    # Turn 1 History:
    {
        "role": "assistant",
        "tool_calls": [{"name": "place_coffee_order", ...}],
    },
    {"role": "tool", "content": '{"ok": true, "order_id": "ORD-508"}'},
    {
        "role": "assistant",
        "content": "Your order for Dark Roast Coffee is placed!",
    },  # <-- Assistant text turn after tool response
    # Turn 2 User Input:
    {"role": "user", "content": "light works"},
]
```

#### ⚡ Technical Root Cause: Gemini Role Sequence Validation
Google Vertex AI / Gemini API enforces strict function calling state machine rules:
> *"Please ensure that function call turn comes immediately after a user turn or after a function response turn."*

* **OpenAI (GPT-4)** permits an `assistant` text turn following a `tool` response turn before the next `user` input.
* **Google Gemini (Vertex AI)** strictly forbids `assistant` text turns between a `tool` response turn and subsequent tool-enabled LLM requests.

Because Rasa Mantle preserved the intermediate `assistant` text turn in the tracker history, Vertex AI's API parser flags the payload as `400 INVALID_ARGUMENT`.

---

### System-Wide Report Cross-Reference
- This issue is also documented in system feedback: [`skills/place_customer_order/RASA_MANTLE_FEEDBACK.md`](file:///Users/samrudhakelkar/Documents/ai/projects/rasa_agent_v1/coffee-shop/skills/place_customer_order/RASA_MANTLE_FEEDBACK.md).

---

### Workaround & Status
- **Status**: Documented & reported to core platform team.
- **Workaround**: Reset the conversation session between multi-turn tool interactions, or sanitize the tracker message history before passing to Vertex AI to strip post-tool assistant text turns.
