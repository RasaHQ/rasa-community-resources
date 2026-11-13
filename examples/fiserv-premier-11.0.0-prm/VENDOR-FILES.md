# Vendor files this example was tested with

Fiserv publishes the Banking Hub Premier definitions as one ZIP, `BankingHub_Premier_api_specs.zip`. Its download address always serves the current file. This table is our own record of the exact archive this example was tested with, and of the five definitions inside it that the example reads. Old rows stay as history.

## Current: Premier 11.0.0_PRM specifications as downloaded 12 Nov 2026

The download sends no Last-Modified date, so this version is named by the date we retrieved it. This example is tested with these exact files.

| File | sha256 |
|---|---|
| BankingHub_Premier_api_specs.zip, from https://developer.fiserv.com/api/download-api-zip/openapi/BankingHub?filename=BankingHub_Premier_api_specs.zip&branch=main | `65404b27b99d12bedc5cddf5d714dc6117d2d4fb3896e7d18d3067e324f4f7a8` |
| inside it: Accountholder/PartyAcctRelService-11.0.0_PRM-Inq_ByParty.yaml | `c9de4806467223179c0208d7b44781e3b2a8b642f4612664bd356ac2595ceab8` |
| inside it: Accounts/AcctService-11.0.0_PRM-Inq_DDA.yaml | `7f7f5477a7cd9e482857dbf2f2d6780b5fd47abb9ec89a637d61c5a5412d62b4` |
| inside it: Accounts/AcctService-11.0.0_PRM-Inq_LOAN.yaml | `55d60b2ab23714821bed9510c9d2d94175bd13ca220bbb9be700490a472569c9` |
| inside it: Transactions/AcctTrnService-11.0.0_PRM-Inq_DDA.yaml | `349840d8eba2444fcb0da5fda2512c9c4f524b38550a383dac6174eda7dfe772` |
| inside it: Transfers/XferService-11.0.0_PRM-Add_Immediate.yaml | `2c151366144ff8aae930311ae5a51798b0038e39ef776878ae8bb14b8a16ed99` |

What changed between versions is in [CHANGELOG.md](CHANGELOG.md).

## If you download a different archive

At start, the example compares your archive and the five definitions with the hashes above. If they differ, it does not stop straight away. It checks its own recorded traffic against your definitions, using the same OpenAPI validators it uses while running. The traffic is in `premier_demo/recorded_exchanges.py`, all fictional data:

- the `EFXHeader` and every request it sends to the five operations;
- the reply it reads from each one.

If your definitions still accept all of it, the example starts and prints: "Your Fiserv download differs from the one this example was tested with (…); everything this example uses is unchanged."

If they do not, or a definition or operation is missing, it stops and names the operation and what the definitions no longer accept. If the check itself cannot run on your files, it stops with "Could not check". Then this example needs an update: please open an issue.

The check is about the shape of the data. If Fiserv changed what a field means but kept its shape, the check cannot see it.
