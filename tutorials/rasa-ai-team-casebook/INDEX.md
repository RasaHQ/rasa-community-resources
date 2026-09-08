# Case index

Each scenario has three explicit evidence predicates and ten expected fixture outcomes.
The receipt is synthetic; the stated real-service boundary is an integration exercise.

| Case | Distinct failure | Evidence owner |
| --- | --- | --- |
| [Advisor bookings with the right purpose](examples/banking-advisor-appointment.json) | The system booked a branch visit for a question requiring a specialist who was not available at that branch. | advisor scheduling owner |
| [Blocking the intended card](examples/banking-block-card.json) | The caller reported one lost card, but the agent blocked every card associated with the account. | card service owner |
| [Card replacement with address provenance](examples/banking-card-reissue.json) | A caller supplied a new delivery address, and the agent treated it as if the bank had already verified it. | card fulfilment owner |
| [Collections with a hardship exit](examples/banking-collections.json) | The agent continued pressing for a plan after the customer explained they could not meet basic expenses. | collections support owner |
| [Disputes without premature reimbursement](examples/banking-dispute.json) | The customer said they did not recognize a charge, and the agent announced a refund before any review occurred. | disputes case owner |
| [Loan servicing with dated quotes](examples/banking-loan-servicing.json) | The agent reused yesterday’s balance as today’s final payoff amount and promised the loan would close. | loan servicing owner |
| [Stopping the right recurring instruction](examples/banking-recurring-payments.json) | The agent cancelled a standing order when the caller meant to stop a merchant subscription. | recurring payments owner |
| [Risk-triggered verification changes](examples/banking-risk-step-up.json) | A session verified for a balance enquiry later attempted a changed-address transfer without another check. | identity risk owner |
| [Transaction search with bounded answers](examples/banking-statement-search.json) | A search for March spending included a pending April item and presented the total as a statement balance. | transaction history owner |
| [Transfers with authoritative balances](examples/banking-transfer.json) | The agent reused a balance read before another debit and promised a transfer the ledger could not fund. | payments ledger owner |
| [Evaluation that checks the actual case](examples/case-evaluation.json) | The dashboard reported a perfect score because every test used the same happy-path fixture. | evaluation lead |
| [Handoff with usable context](examples/contextual-handoff.json) | The agent announced a transfer, but no desk had accepted the case; the customer repeated the whole story in a new queue. | support integration owner |
| [Disruption mode without false promises](examples/disruption-mode.json) | The agent promised seats to two callers while availability updates lagged behind a storm cancellation. | disruption incident commander |
| [Enrolment support without aid guarantees](examples/education-enrolment.json) | The assistant treated a submitted aid form as an award decision and told the applicant that funding was secured. | student services owner |
| [Clinic bookings that match the service](examples/healthcare-booking.json) | The scheduler offered the first free slot even though that appointment type could not provide the requested service. | clinic scheduling owner |
| [Pre-visit intake with uncertain eligibility](examples/healthcare-intake.json) | An insurance lookup returned an uncertain result, but the agent told the patient the visit would definitely be paid for. | patient access owner |
| [Reminder responses without inferred attendance](examples/healthcare-no-show-reminder.json) | A voicemail delivery was counted as patient confirmation, and the clinic assumed the appointment would be attended. | clinic outreach owner |
| [Refill requests without prescribing](examples/healthcare-refill-request.json) | The agent said a medication was renewed when it had only collected a request for the prescribing team. | prescribing workflow owner |
| [Results notifications with a verified recipient](examples/healthcare-result-notification.json) | The agent read a result to a family member who answered the phone and knew the patient’s name. | clinical communications owner |
| [Clinical questions routed without diagnosis](examples/healthcare-routing.json) | The routing agent turned a short symptom description into a reassuring diagnosis and delayed the human route. | clinical routing owner |
| [Payment status before lapse messaging](examples/insurance-billing.json) | A bank transfer was pending, but the agent treated an unpaid invoice label as proof that cover had lapsed. | premium billing owner |
| [Claim intake with a submission receipt](examples/insurance-file-claim.json) | The customer supplied the story, but a failed upload left the claim unrecorded while the agent said it was filed. | claims intake owner |
| [First loss reports with an urgent exit](examples/insurance-fnol.json) | The intake assistant kept requesting photographs while the caller was describing an unsafe roadside situation. | first-notice operations owner |
| [Policy status without coverage promises](examples/insurance-policy-status.json) | The agent read an active policy label and told the caller that a particular loss would be covered. | claims service owner |
| [Quotes that do not silently bind](examples/insurance-quote-bind.json) | The agent described an indicative estimate as active cover before the underwriting service had returned a binding receipt. | underwriting integration owner |
| [Renewal offers with clear effective dates](examples/insurance-renewal.json) | The customer selected a cheaper renewal, but the agent omitted the changed deductible and effective date. | renewal product owner |
| [Roadside dispatch with a confirmed location](examples/insurance-roadside.json) | The agent sent a provider to the registered home address instead of the vehicle’s current location. | assistance dispatch owner |
| [Field assignments with capability and safety state](examples/internal-field-dispatch.json) | A dispatcher agent sent the nearest technician even though the job required equipment that technician did not carry. | field dispatch owner |
| [HR requests without inferred entitlement](examples/internal-hr.json) | The agent showed a leave balance and described the requested dates as approved time off. | HR service owner |
| [Invoice status without payment authority](examples/internal-invoice-status.json) | The assistant interpreted a matched purchase order as permission to release payment to newly supplied bank details. | finance operations owner |
| [Helpdesk requests with least authority](examples/internal-it-helpdesk.json) | The helpdesk agent granted an access role because the employee described it as urgent and mentioned their manager. | enterprise access owner |
| [Hands-free CRM notes with a review boundary](examples/internal-sales-notes.json) | A dictated customer comment was stored as an agreed contract term on the wrong opportunity. | sales systems owner |
| [Shift changes that preserve qualified coverage](examples/internal-shift-swap.json) | The agent approved a swap between two available people without checking whether the replacement held the required qualification. | workforce scheduling owner |
| [Language switches that preserve intent](examples/language-switch.json) | The agent switched language midway through a permit request and lost the caller’s earlier correction to the address. | conversation localization owner |
| [Driver check-in with site authorization](examples/logistics-driver-check-in.json) | The agent marked a driver cleared for loading because it recognized the carrier name, despite a different vehicle and slot. | yard operations owner |
| [Failed-delivery follow-up without address leakage](examples/logistics-failed-delivery.json) | An outbound agent read the full delivery address to an unverified person who answered a shared phone. | delivery outreach owner |
| [Delivery changes with a dispatch cutoff](examples/logistics-reschedule.json) | The agent confirmed a new delivery window after the vehicle had already left on a route that could not be changed. | carrier integration owner |
| [Outbound contact permission](examples/outbound-permission.json) | A shopper withdrew permission after a list was exported, but the dialer still called from the old campaign file. | outbound operations owner |
| [Payment-plan offer authority](examples/payment-plan-authority.json) | The agent promised a smaller instalment than the billing service allowed and marked the account resolved. | billing policy owner |
| [Citizen requests with the correct jurisdiction](examples/public-citizen-services.json) | The agent gave a permit answer from a neighbouring authority and presented it as binding for the caller’s address. | citizen service owner |
| [Reminders without duplicate calls](examples/reminder-deduplication.json) | A rescheduled appointment generated both the old reminder and the new one, sending the patient to the wrong time. | appointment messaging owner |
| [Cart follow-ups with current terms](examples/retail-cart-recovery.json) | An abandoned-cart call promised an expired discount and continued after the shopper withdrew contact permission. | commerce outreach owner |
| [Product choices with evidence boundaries](examples/retail-guided-selling.json) | The agent recommended a compatible accessory based on a similar product name, but its connector did not fit. | product catalogue owner |
| [Subscriptions without hidden entitlement loss](examples/retail-loyalty.json) | The agent cancelled a subscription immediately when the member meant to stop its next renewal. | subscription product owner |
| [Order status with a carrier timestamp](examples/retail-order-status.json) | The agent called an order delivered because a warehouse label existed, although the carrier had not collected it. | fulfilment visibility owner |
| [Returns with eligibility and receipt boundaries](examples/retail-return.json) | The agent promised a refund as soon as it generated a return label, before the item had been received or reviewed. | returns service owner |
| [Step-up authentication](examples/step-up-authentication.json) | The caller supplied a familiar employee name, and the agent treated familiarity as permission to reset access. | identity platform owner |
| [Diagnostics before disruptive resets](examples/telco-diagnostics.json) | The agent factory-reset a router while the customer only wanted the status of a known area outage. | network support owner |
| [Outage messages with a current incident](examples/telco-outage-notification.json) | The notification said service was restored even though the customer’s access segment remained affected. | network incident owner |
| [Plan changes with an explicit price delta](examples/telco-plan-change.json) | The agent quoted the monthly price but omitted that the roaming add-on began after the customer’s trip. | plan catalogue owner |
| [Retention that respects the exit](examples/telco-retention.json) | The caller asked to stop the conversation, but the retention agent continued cycling through discounts. | retention operations owner |
| [SIM changes with an independent challenge](examples/telco-sim-swap.json) | The agent accepted a verification code sent only to the phone number whose SIM was being replaced. | subscriber identity owner |
| [Technician visits without lost bookings](examples/telco-technician-slot.json) | The old appointment was cancelled before the replacement slot was secured, leaving the customer with no visit. | field appointment owner |
| [Journey changes with linked services](examples/travel-booking.json) | The agent changed one flight segment and left a connecting service pointing at the old arrival time. | journey servicing owner |
| [Hotel extras without changing the booking](examples/travel-hotel.json) | The agent promised late checkout because it appeared in a brochure, although the property had no availability that day. | hotel ancillary owner |
| [Rebooking during a mass disruption](examples/travel-mass-rebooking.json) | A storm response offered the same last seat to many passengers and confirmed each before capacity was committed. | disruption recovery owner |
| [Rewards redemption with held inventory](examples/travel-redemption.json) | Points were deducted even though the selected reward seat disappeared before booking completed. | rewards ledger owner |
| [Budget plans with a hardship boundary](examples/utilities-budget-plan.json) | The agent treated an estimated budget instalment as a waiver of the customer’s outstanding balance. | customer billing support owner |
| [Meter readings with provenance and units](examples/utilities-meter-reading.json) | The system accepted a reading for the wrong meter and interpreted a decimal value as whole units. | meter data owner |
| [Outage reports without repair estimates](examples/utilities-outage.json) | The agent invented a repair time from an old incident even though the new report affected a different service area. | outage coordination owner |
| [Service moves without premature closure](examples/utilities-service-move.json) | The agent closed the current service immediately when the customer requested a move next month. | service lifecycle owner |
| [Payment capture boundaries](examples/voice-payment-boundary.json) | The caller started reading card details, and the conversation recorder captured them before payment processing began. | payments integration owner |
