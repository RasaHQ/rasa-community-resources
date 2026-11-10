"""Print deterministic SDK/application controls, not a live conversation."""
import json
import httpx2
from typesafe_sdk import RetryPolicy, TypeSafeClient
from .accounts import Accounts
from .scripted import scripted_transport
from .selector import MODEL, Selector, question


def main():
    # A well-shaped wire reply can name an unoffered option. This is a decoder
    # control, not a prediction obtained from Jev's hosted service.
    accounts = Accounts()
    offered = question(accounts.snapshot("demo-a"))
    def unoffered_reply(request):
        return httpx2.Response(200, json={"model": MODEL,
            "usage": {"input_tokens": None, "output_tokens": None},
            "answers": {"account": {"type": "choice", "choice": "B-CURRENT",
                "confidence": 1.0, "probabilities": {"A-CURRENT": 1.0,
                    "A-SAVINGS": 0.0, "ask_customer": 0.0}}}})
    with TypeSafeClient(api_key="scripted-local-test", base_url="https://scripted.invalid",
                        model=MODEL, transport=httpx2.MockTransport(unoffered_reply),
                        retry=RetryPolicy(max_retries=0)) as client:
        result = client.system_one(model=MODEL, state={"customer_message": "Current"},
                                   questions={"account": offered})
        choice = result.choices["account"].choice
        guarded = Selector(client, accounts).select("demo-a", "Current")
    print(json.dumps({"control": "unoffered_wire_choice", "sdk_decoded_choice": choice,
                      "choice_was_offered": choice in offered.criteria,
                      "application_status": guarded["status"], "account_reads": accounts.reads,
                      "external_provider_requests": 0}, sort_keys=True))
    for mode in ("current", "retired_during_decision", "clarify", "wrong_eligible"):
        accounts = Accounts()
        transport, requests = scripted_transport(
            "ask_customer" if mode == "clarify" else "A-SAVINGS" if mode == "wrong_eligible" else "A-CURRENT",
            (lambda: accounts.retire("A-CURRENT")) if mode == "retired_during_decision" else None)
        with TypeSafeClient(api_key="scripted-local-test", base_url="https://scripted.invalid",
                            model=MODEL, transport=transport, retry=RetryPolicy(max_retries=0)) as client:
            result = Selector(client, accounts).select("demo-a", "Show my current account transactions")
        record = {"control": mode, "status": result["status"], "account_reads": accounts.reads,
                  "sdk_requests": len(requests), "external_provider_requests": 0}
        if mode == "wrong_eligible":
            record.update(requested_account="A-CURRENT", selected_account=result["account"])
        print(json.dumps(record, sort_keys=True))


if __name__ == "__main__":
    main()
