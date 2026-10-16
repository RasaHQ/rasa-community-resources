# Test confirmation after a payment offer changes

Your billing assistant offers a customer three monthly payments. While the
customer considers it, the billing service can issue different terms. Before
recording the plan, you need to check which offer the customer was asked to approve.

You will change the offer, refresh the saved values and see why the earlier
question still does not refer to the new terms. Then you will supply a fresh
fixture question and inspect the recorded plan. Amber Grid and its billing
records are fictional.

This is an offline service exercise. It needs Python and the supplied project
files, with no SDK installation, model, licence key or network. Conversation
objects are test fixtures: they do not demonstrate Mantle's pause/resume or
affirmative-answer handling. The engine's confirmation gate is a separate
integration boundary.

## Run from the project directory

```sh
make offer-change
```

The command writes a JSON report. Compare `originalOffer` and `revisedOffer`:
the original has three payments of 214.00 USD; the revised offer has three
payments of 200.00 USD and a new revision. The code changes both fields together,
so this is not an isolated test of either field alone.

The three stages show:

| Stage | Saved values | Question | Service result | Plans recorded |
| --- | --- | --- | --- | --- |
| First attempt | Original | Original | `unapproved_terms` | 0 |
| Values refreshed | Revised | Original | `acceptance_missing` | 0 |
| Question replaced | Revised | Revised fixture | `succeeded` | 1 |

Focus on the second row. The report shows the current authorised offer and
current revision both resolving true. The question evidence still resolves
false. Compare its `savedOfferTag` and `savedTerms` with the old `question`:
updating memory did not change what that question asked.

The third stage keeps the same revised service offer and saved values.
It changes the fixture question and later-message evidence. Inspect
`recordedTerms` to check that the service copied 200.00 USD from its offer.
The lowered amount does not cause this fixture to reuse the old question.

The fixture has a fixed `as_of` clock, shown as `fixtureClock`; expiry does
not depend on the day you run it. That is test data, not a changed site
publication clock or a record of today's billing offer.

## Follow the check

Read `acceptance_facts` and `accept_plan_offer` in `lib/plans.py`.
They compare service-owned terms and revision with saved values and the
question's displayed offer tag and terms. The service copies recorded terms
from its own offer; the acceptance tool does not accept a model-written amount.

Run the regression and the existing offline guard suite:

```sh
python3 -m unittest discover -s tests -p test_changed_offer_exercise.py -v
make proof
```

Without the SDK, the two existing SDK-dependent guard checks skip. Those
skips do not establish native integration. Use the parent README's separate
SDK validation, training and conversation procedure when you need that evidence.

If a command fails, keep the error and check that source and exercise came
from the same reviewed revision. Do not edit the expected outcome to obtain a
pass. No test should create a billing record outside its own in-memory service.

## Apply the distinction

If the service offers a cheaper plan while a customer answers, is refreshing
the assistant's saved values sufficient?

The second stage shows why it is not sufficient here: the displayed question
still names the earlier offer. In your integration, test the actual dispatcher
and confirmation response as well. A production billing service must also
compare and record its offer revision atomically; this sequential in-memory
fixture does not demonstrate concurrency safety or any legal consent standard.
