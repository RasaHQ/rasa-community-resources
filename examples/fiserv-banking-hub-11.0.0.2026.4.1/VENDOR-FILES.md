# Vendor files this example was tested with

Fiserv publishes the Banking Hub API definitions as one release ZIP, named by its release number. This table is our own record of the exact archive this example was tested with, and of the four definitions inside it that the example reads. Old rows stay as history.

## Current: Fiserv Banking Hub release 11.0.0.2026.4.1, as pinned 12 Nov 2026

The release is named by its number. The archive was first pinned on 12 Nov 2026. This example is tested with these exact files.

| File | sha256 |
|---|---|
| esf-service-swagger-release-11.0.0.2026.4.1.zip, from Fiserv's Banking Hub Resources page, https://developer.fiserv.com/product/BankingHub/docs/resources/resources.md?branch=main ("Download API Specifications (v11.0.0.2026.4.1)") | `844bb52475f442da9b96a093c3443c4d9b6a47e7c9834c509f0cf92a117f2fd3` |
| inside it: src/swagger/Bank_Sol_Org-PartyAcctRelService-11.0.0-resolved.yaml | `75abe3ac04300b85e176e48acaccf6597380dfab22cda4c6d4005a318cacb8c2` |
| inside it: src/swagger/Bank_Sol_Org-AcctService-11.0.0-resolved.yaml | `3bcc50c8bb22e633c7cec484cd2d4216a677bbcb8d0759740d92fdce31b5e365` |
| inside it: src/swagger/Bank_Sol_Org-AcctTrnService-11.0.0-resolved.yaml | `1eb4d5a8a98a2be84d47356716055cf3d0e49a376e4f78056aa5e9830366267f` |
| inside it: src/swagger/Bank_Sol_Org-XferService-11.0.0-resolved.yaml | `ff1a683ae0bbc4ff755a9c9bc1896198a2695a6483c4552e805642c19085f0da` |

These are the same values `bh_demo/contract.py` checks. What changed between versions is in [CHANGELOG.md](CHANGELOG.md).

## If you download a different archive

Today this example accepts only the archive above. If your file differs, it stops at start-up with "Not ready." and asks you to download the release again. It does not yet check whether a different archive would still work; that check, as the other bank examples have, is planned.
