"""Run actual local Laya decisions, then exercise proposal confirmation."""
import json
from typesafe_sdk import RetryPolicy, TypeSafeClient
from .accounts import Accounts
from .selector import LOCAL_MODEL, Selector
from .proposals import Proposals


def main():
    with TypeSafeClient(api_key="local-loopback", base_url="http://127.0.0.1:5031",
                        model=LOCAL_MODEL, timeout=10, retry=RetryPolicy(max_retries=0)) as client:
        for message, confirm in [("Show my current account transactions", True),
                                 ("Show my savings account transactions", True),
                                 ("Show my account transactions", False)]:
            accounts = Accounts()
            service = Proposals(Selector(client, accounts, model=LOCAL_MODEL))
            proposal = service.propose("demo-a", "local-example", message)
            before = list(accounts.reads)
            if proposal["status"] == "account_proposal":
                operation = service.confirm if confirm else service.cancel
                outcome = operation("demo-a", "local-example", proposal["proposal_token"])
            else:
                outcome = proposal
            print(json.dumps({"kind": "actual-local-model", "message": message,
                              "proposal_status": proposal["status"], "proposed_account": proposal.get("account"),
                              "reads_before_confirmation": before, "outcome": outcome["status"],
                              "reads_after_reply": accounts.reads, "model": LOCAL_MODEL}, sort_keys=True))


if __name__ == "__main__":
    main()
