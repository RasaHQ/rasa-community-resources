# concern: refill-guard
"""The refill guard as a Strands intervention handler.

Strands' interventions (strandsagents.com/docs/user-guide/sdk/agents/interventions/)
return typed decisions before a tool runs. ``RefillGuard.before_tool_call``
answers every ``send_refill_request`` call:

- ``Deny`` when no patient was verified, no medication is selected, or the
  call names another entry than the one ``select_medication`` wrote to
  ``agent.state``. The model sees the reason; nothing runs. Fails closed.
- ``Confirm`` otherwise, with ``cedar_clinic``'s read-back question as the
  prompt. With no response given, Confirm raises a Strands interrupt: the
  agent stops with ``stop_reason == "interrupt"``, the voice loop speaks the
  prompt, and the agent is resumed only with the caller's words from their
  next turn (``agent.Conversation.turn``). ``evaluate`` then judges those
  words, records the answer with the clinic and lets the tool run only on a
  yes. A no cancels the call (``CONFIRMATION_FAILED``).

``after_tool_call`` adds the caller's answer to the tool result: a resumed
agent gets interrupt responses, not a user message, so this is how the model
learns what the caller said at the confirmation (for example, another
medicine's name).

``on_error`` is ``deny``: if the handler raises, the send is blocked.
"""

from __future__ import annotations

import re
from typing import Any, Optional

from cedar_clinic import refills
from cedar_clinic import tools as clinic
from strands.interventions import Confirm, Deny, InterventionHandler, Proceed, Transform

MECHANISM = "strands Confirm intervention (interrupt, resumed with the caller's next turn)"

_AFFIRM_START = re.compile(
    r"^(yes|yeah|yep|yup|sure|ok|okay|fine|alright|all right|correct|right|absolutely|definitely|please( do| send)?|go ahead|"
    r"that's (right|correct|the one|it)|that is (right|correct)|send it|do it)\b")
_NEGATION = re.compile(r"\b(no|nope|not|don't|dont|do not|wait|cancel|stop|instead|wrong|hold on|never mind)\b")
_LATER_NEGATION = re.compile(r"\b(don't send|do not send|not that|wait|cancel|instead|wrong|hold on|never mind)\b")
_DRUG_NAMES = sorted({str(m["name"]).lower() for m in refills.load_data()["medications"].values()})


def caller_said_yes(answer: Any, medication_label: str) -> bool:
    """Whether the caller's words approve the read-back. Anything unclear is a no.

    Yes only when the first clause starts with an affirmative and has no
    negation, no later clause retracts it, and no other recorded medicine is
    named.
    """
    text = str(answer or "").lower().replace("’", "'").strip()
    if not text:
        return False
    first = re.split(r"[.,!?;]", text, maxsplit=1)[0].strip()
    if not _AFFIRM_START.search(first) or _NEGATION.search(first) or _LATER_NEGATION.search(text):
        return False
    label = medication_label.lower()
    return not any(re.search(rf"\b{re.escape(name)}\b", text) and name not in label for name in _DRUG_NAMES)


def _answer(response: Any) -> str:
    return str(response.get("answer", "")) if isinstance(response, dict) else str(response or "")


class RefillGuard(InterventionHandler):
    name = "refill-guard"

    def __init__(self, conversation_id: str) -> None:
        self.conversation_id = conversation_id
        #: toolUseId -> (answer, confirmed) for the confirmations evaluated.
        self.answers: dict[str, tuple[str, bool]] = {}

    @property
    def on_error(self) -> str:
        return "deny"

    def before_tool_call(self, event: Any):
        if event.tool_use["name"] != "send_refill_request":
            return Proceed()
        state = event.agent.state
        patient: Optional[str] = state.get("patient_id")
        selected: Optional[str] = state.get("selected_record_id")
        label: str = state.get("selected_medication_label") or ""
        record_id = str((event.tool_use.get("input") or {}).get("record_id") or "").strip().upper()
        if not patient:
            return Deny(reason="The caller is not verified. Call verify_patient first. Nothing was sent.")
        if not selected:
            return Deny(reason="No medication is selected. Call select_medication first. Nothing was sent.")
        if record_id != selected:
            return Deny(reason=f"Only the medication select_medication returned can be sent: record_id {selected}. "
                               "Nothing was sent.")
        question = clinic.confirmation_question(label)
        tool_use_id = str(event.tool_use.get("toolUseId"))

        def evaluate(response: Any) -> bool:
            answer = _answer(response)
            confirmed = caller_said_yes(answer, label)
            clinic.record_confirmation(self.conversation_id, record_id, confirmed, mechanism=MECHANISM,
                                       question=question, answer=answer)
            self.answers[tool_use_id] = (answer, confirmed)
            return confirmed

        return Confirm(prompt=question, evaluate=evaluate)

    def after_tool_call(self, event: Any):
        tool_use_id = str(event.tool_use.get("toolUseId"))
        if event.tool_use["name"] != "send_refill_request" or tool_use_id not in self.answers:
            return Proceed()
        answer, confirmed = self.answers[tool_use_id]

        def add_answer(e: Any) -> None:
            note = f'The caller answered the read-back question: "{answer}".'
            if not confirmed:
                note += (f' Nothing was sent, and the caller has been told: "{clinic.DECLINED_TEXT}" If they named '
                         "a different medicine, call select_medication for it.")
            e.result["content"] = list(e.result.get("content") or []) + [{"text": note}]

        return Transform(apply=add_answer)

    def declined_on(self, tool_result: dict) -> bool:
        """Whether this send_refill_request result is a declined confirmation."""
        answer = self.answers.get(str(tool_result.get("toolUseId")))
        return answer is not None and not answer[1]
