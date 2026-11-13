# Vendor files this example was tested with

Jack Henry publishes the jXchange definitions as a ZIP named after its release. This table is our own record of the exact archive this example was tested with. Old rows stay as history.

## Current: TPG R2026.1.00 XSD archive as published 3 Nov 2026

Retrieved 12 Nov 2026. This example is tested with this exact archive.

| File | Address | sha256 | Last-Modified |
|---|---|---|---|
| TPG_R2026.1.00_XSD.zip | https://jkhy.github.io/devrel-assets/cms-files/soap/TPG_R2026.1.00_XSD.zip | `a433a01b05925bd9af2bb12184046443574eba98c4fbf65b716b73cad6ff7900` | Tue, 03 Nov 2026 17:40:36 GMT |
| inside it: TPG_Inquiry.wsdl | | `f2ff471b945b938ae0173ba2174eeb9fbb30c678c3232f177566bb27143b5108` | |
| inside it: TPG_Transaction.wsdl | | `559ce0113d96260ce4f7437c0dfd3a6ad49c0d976fc29abfdfaa31680dafbd22` | |

What changed between versions is in [CHANGELOG.md](CHANGELOG.md).

## If you download a different archive

At start, the example compares your archive with the hashes above. If it differs, it does not stop straight away. It checks exactly what it uses:

- the SOAPAction of each of its six operations in the WSDLs;
- every request it sends and every reply it reads, for each of the six operations. It builds them with its own client and mock, in memory, and validates each element against the schemas in your archive.

If all of that still fits, it starts and prints: "Your Jack Henry download differs from the one this example was tested with (…); everything this example uses is unchanged." If something no longer fits, it stops and names the operation. Then this example needs an update: please open an issue.

This is a check of shape only. If Jack Henry changed what an element means but kept its shape, the check cannot see it.
