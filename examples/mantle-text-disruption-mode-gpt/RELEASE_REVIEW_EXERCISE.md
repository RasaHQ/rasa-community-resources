# Bind a release decision to one question

This constructed exercise compares application checks against the existing
fictional Horizon inventory service. It is outside the Mantle tool surface:
`exercises/release_decision.py` models a separate channel or application layer.
No native integration hook is implemented here. The historical `lib`, `tools`
and `skills` files remain unchanged.

From this example's directory, with Python 3.12:

```sh
python3 -m unittest discover -s tests -p test_release_review.py -v
python3 case-build/release_policy_comparison.py
```

The comparison prints three constructed paths using the same fixture:

- Direct service: deliberately call release after a refused application
  decision. This establishes what the service's ownership checks permit;
  it is not a claim that the recorded model ignored a refusal.
- Unbound-answer control: a deliberate mutation applies an old answer to
  whichever question is current. The controller otherwise uses the same
  state checks and service as the bound path. It does not reproduce the
  historical model's interpretation of a conversational Yes.
- Bound application decision: retain the question identifier and reject an
  answer for a superseded question before changing any hold.

Inspect final holds and inventory as well as each returned receipt. In the
correction comparison, first propose releasing Miami, then propose releasing
an independently created Chicago hold. Send acceptance for the old Miami
question. The unbound control should release Chicago; the bound path should
retain both holds until the current question is accepted. Replaying that
accepted decision should return its receipt without returning another seat.
These are expectations to check against actual output, not recorded results.

The nine regression tests cover refusal, an unknown question, correction,
replay, ownership, the direct-service control, accept after refusal,
re-asking about the same hold and the deliberately unbound control.

`ReleaseReview.decide` belongs behind the authenticated application's user
interface. A model-supplied `accept` string would not establish passenger
permission. Proposal identifiers identify questions; they are not secrets or
authentication tokens. The passenger identity is fixed by the server-side
session when the controller is constructed.

The cost is an application-owned confirmation interface and one structured
decision for each proposal. A correction retires the first question and needs
a new decision. The tests inject those decisions; they do not measure human
understanding or questions asked in a deployed conversation.

Mantle's native `requires_confirmation` declaration is a separate option.
`tests/test_release_gate_characterisation.py` checks the shipped declaration
and compiles temporary added/removed declarations when the SDK is installed.
That is compiler evidence, not execution of a newly gated release. This
exercise neither compares native release runtime behaviour nor establishes
that the application controller is preferable to the native mechanism.

The controller is an in-memory, single-process teaching fixture. It does not
implement persistence, expiry, concurrent requests or transport authentication.
It rechecks ownership and current hold state through the existing service.
A real integration needs those missing application controls and its own
end-to-end tests. Run the complete project proof separately before describing
the whole project as qualified. No result for this new exercise is recorded yet.
