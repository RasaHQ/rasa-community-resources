# Illustrative mappings, not vendor adapters

Mocks follow the shared banking contract; vendor mappings are illustrative, based on public documentation, and not tested against vendor systems.

The conformance target is our `banking` contract version `1.0.0`, not a vendor
schema. Both configurations use our own field names and fictional values.
Vendor wire fields and bindings are unknown. No vendor schema or derived schema
is bundled, no vendor certification is claimed, and no vendor endpoint is called.

| Our action | Jack Henry illustrative operation | Fiserv illustrative area |
|---|---|---|
| `banking_accounts` | jXchange `AcctSrch` | Banking Hub / Communicator Open account inquiry; exact operation unknown |
| `banking_balance` | jXchange `AcctBalInq` | Account balance inquiry; exact operation unknown |
| `banking_history` | jXchange `AcctHistSrch` | Account transaction inquiry; exact operation unknown |
| `banking_loan_payment` | jXchange `LnPmtSchedInq` | Loan/payment inquiry; exact operation unknown |
| `banking_payoff` | jXchange `LnPayoffInq` | Loan payoff inquiry; exact operation unknown |
| `banking_review_transfer` | Our local review; no bank submission | Our local review; no bank submission |
| `banking_submit_transfer` | jXchange `XferAdd` candidate | Own-account transfer area; exact operation unknown |
| `banking_transfer_status` | Our retained operation state; vendor inquiry unknown | Our retained operation state; vendor inquiry unknown |

Jack Henry's public [SilverLake catalogue](https://jackhenry.dev/jxchange-soap/api-provider/silverlake/)
and [service reference](https://jackhenry.dev/jxchange-soap/all-services/) name
these operations. The mapping does not assert every provider/profile supplies
every field or dated quote. Symitar/SymXchange equivalents remain unknown; its
[service index](https://jackhenry.dev/symxchange-api-docs/wsdl-episys-records/)
describes a separate SOAP binding. No SilverLake binding is silently reused for it.

Fiserv's public [AppMarket FAQ](https://appmarket.fiservapps.com/faq) describes
Banking Hub and Communicator Open across cores including DNA and Premier. Those
product descriptions motivate the illustrative areas above; they are not exact
operation names, field mappings or verified DNA/Premier compatibility. Neither
core is certified by the synthetic results in `fiserv.json`.

Mock balances, history, payment dates and the one supplied payoff date are
authored teaching data. A queued or accepted transfer does not change balances
or claim posting. A future real-vendor path requires separately chosen contracts,
rights, account access and qualification; there is no live-bank mode here.
