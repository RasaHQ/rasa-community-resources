---
name: deploy_gate
description: >
  Deploy a project to staging or production, but only after checking that no
  critical tickets are open on it. Activate when they ask to deploy, ship,
  or release a service.
requires: session.project.authenticated
tool_constraints:
  - check_deploy_blockers:
      requires: session.deploy_gate.project_name
  - record_deployment:
      requires: session.deploy_gate.blockers_checked
      requires_confirmation:
        enabled: true
        utter_for_confirmation: utter_confirm_deployment
        utter_on_user_denial: utter_deploy_cancelled
      on_success: utter_deploy_recorded
---

Help the developer deploy one of their projects safely.

The very first thing you must do is ask for their badge number to verify
identity. Do not ask which project or environment until after authentication.
Say: "Before I can deploy, I need to verify your identity. What is your
badge number?" Once they provide it, call @skill.authenticate.

After authentication succeeds, ask which project they want to deploy and set
project_name. Then ask whether it is going to staging or production and set
environment.

Call check_deploy_blockers for the project before anything else.

if: session.deploy_gate.blocked == True
Say the deploy is blocked. Name each critical ticket still open on the
project, and offer @skill.ticket_notes to work on them first. Do not deploy.

if: session.deploy_gate.blocked == False
Say the coast is clear, then call record_deployment. Read the deployment
reference character by character when it succeeds.
