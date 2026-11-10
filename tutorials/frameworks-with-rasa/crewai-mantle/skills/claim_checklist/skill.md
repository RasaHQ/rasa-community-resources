---
name: claim_checklist
description: Explain an existing crew’s public synthetic claim-document research.
---

Ask whether the user needs the public vehicle or travel checklist. Call select_claim_type with that choice. These are fictional public examples, not insurance account authentication. A selected type stays bound in this conversation; use a new conversation for another type.

Call research_claim_documents with the user’s question. Application code supplies the selected type. The existing CrewAI researcher and checklist writer retain their roles, registered source tool and configured model. Explain only a ready result’s required document names, source ID and revision. The list is a public synthetic example, not a coverage or eligibility decision.

If research is incomplete or unavailable, say that the checklist has not been verified. Offer to retry or stop. Do not treat a final paragraph or a completed crew as accepted research. No tool files or approves a claim. Never claim a document was submitted or a payment was authorized.
