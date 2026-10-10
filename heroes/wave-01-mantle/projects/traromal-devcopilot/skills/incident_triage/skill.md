---
name: incident_triage
description: >
  Investigate a service incident by correlating open tickets and recent
  deployments. Activate when they ask what is wrong with a service, why an
  incident happened, or to triage a production problem.
---

Help triage the incident without making changes.

Collect the service or project name if it was not provided. Then call
triage_incident.

Report the result in this order:

1. Critical and high open tickets on the service.
2. Recent deployments and their status.
3. Whether a recent deployment is a possible change point.
4. The safest next action.

Do not claim that a deployment caused an incident. Say it is a correlation or
possible change point unless an external monitoring tool proves causation.
Offer @skill.escalation when the evidence indicates a critical incident.
