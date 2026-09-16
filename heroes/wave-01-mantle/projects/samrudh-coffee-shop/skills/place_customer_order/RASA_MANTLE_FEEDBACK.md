# Rasa Mantle Engineering Feedback Report

## Issue Summary
- **Component**: `rasa.mantle.orchestration.orchestrator` / `LLMClient` (LiteLLM integration with Google Gemini provider)
- **Error Code**: `400 INVALID_ARGUMENT (Vertex_ai_betaException)`
- **Error Message**: `"Please ensure that function call turn comes immediately after a user turn or after a function response turn."`

---

## Technical Analysis

### 1. What is Happening
During multi-turn dialogues involving tool execution or tool confirmation (`tool_constraints` / `requires_confirmation`), Rasa Mantle's orchestrator constructs a `messages` history payload for LiteLLM.

In certain turn transitions, the `messages` array contains consecutive `assistant` role messages:
```python
messages = [
    {"role": "user", "content": "..."},
    {"role": "assistant", "tool_calls": [{"name": "place_coffee_order", ...}]},
    # MISSING: {"role": "tool", "tool_call_id": "...", "content": "..."}
    {"role": "assistant", "content": "Utterance or confirmation prompt..."}
]
```

Google Gemini's Vertex AI API strictly validates OpenAPI role sequences and throws:
`litellm.BadRequestError: Vertex_ai_betaException BadRequestError - 400 INVALID_ARGUMENT: Please ensure that function call turn comes immediately after a user turn or after a function response turn.`

### 2. Expected Behavior
1. **History Normalization**: Mantle's orchestrator should normalize the conversation transcript before invoking LiteLLM/Gemini, guaranteeing that every `assistant` message with `tool_calls` is immediately followed by a corresponding `tool` role message.
2. **Gated / Confirmation Turn Alignment**: When a tool execution is intercepted by Mantle (such as for user confirmation), Mantle should inject a synthetic `tool` response event (e.g. `{"role": "tool", "content": "status: confirmation_pending"}`) into the LLM context to satisfy provider schema constraints.
3. **Flexible `memory:` Schema Aliases**: `set_fields` currently rejects unlisted field names with `set_fields.not_eligible`. Supporting field aliases or non-strict parameter matching in `memory:` would prevent LLM turn failures when parameter names vary slightly (e.g. `size` vs `selected_size`).

---

## File Reference
- Documented in: [`skills/place_customer_order/skill.md`](file:///Users/samrudhakelkar/Documents/ai/projects/rasa_agent_v1/coffee-shop/skills/place_customer_order/skill.md#L46-L63)
- Test suite: [`tests/e2e/test_deterministic.yml`](file:///Users/samrudhakelkar/Documents/ai/projects/rasa_agent_v1/coffee-shop/tests/e2e/test_deterministic.yml#L26-L37)
