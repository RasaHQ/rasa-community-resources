---
name: safety_escalation
description: >
  Hard escalation for red-flag symptoms this assistant must never answer
  directly: possible hypoglycemia, thyroid crisis, concerning
  menstrual-pattern changes, or disordered-eating signals. Activate
  immediately whenever a red flag is present, or when another skill hands
  off here — never generate a clinical answer for these.
utter:
  - utter_escalate_hypoglycemia:
      when: session.safety_escalation.escalation_type == "hypoglycemia"
  - utter_escalate_thyroid_crisis:
      when: session.safety_escalation.escalation_type == "thyroid_crisis"
  - utter_escalate_menstrual_pattern:
      when: session.safety_escalation.escalation_type == "menstrual_pattern"
  - utter_escalate_disordered_eating:
      when: session.safety_escalation.escalation_type == "disordered_eating"
  - utter_escalate_medication_change:
      when: session.safety_escalation.escalation_type == "medication_change"
  - utter_escalate_diagnosis_request:
      when: session.safety_escalation.escalation_type == "diagnosis_request"
  - utter_escalate_cure_claim:
      when: session.safety_escalation.escalation_type == "cure_claim"
  - utter_escalate_urgent_symptom:
      when: session.safety_escalation.escalation_type == "urgent_symptom"
  - utter_escalate_other:
      when: session.safety_escalation.escalation_type == "other"
---

Set escalation_type based on what triggered this hand-off, before anything
else:
- hypoglycemia — possible low blood sugar.
- thyroid_crisis — possible thyroid emergency.
- menstrual_pattern — a concerning change in menstrual pattern.
- disordered_eating — signs of disordered eating.
- medication_change — any request to start, stop, change, or dose
  medication ("should I stop my diabetes medication?").
- diagnosis_request — asking you to diagnose or confirm a condition ("do I
  definitely have PCOS?").
- cure_claim — asking whether a food can treat or cure a condition ("can
  this food cure insulin resistance?").
- urgent_symptom — a potentially dangerous symptom right now ("I'm feeling
  faint and haven't eaten all day").
- other — a red flag that fits none of the above.

The matching verbatim response plays automatically once it is set —
do not add your own clinical explanation before or after it, and do not
paraphrase it.

Do not attempt to answer the underlying medical question yourself, do not
suggest a diagnosis, and do not suggest a specific treatment or medication
change.

After the escalation message, ask only whether there is anything
non-medical you can still help with.
