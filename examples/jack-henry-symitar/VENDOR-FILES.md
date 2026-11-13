# Vendor files this example was tested with

Jack Henry publishes the Symitar API definitions on jackhenry.dev. Each file has one address that always serves its newest version. There is no address for an older version, so this table is our own record of which versions this example was tested with. Old rows stay as history.

We name each version by when Jack Henry's site last changed it. `Last-Modified` is the date the site sent with the file. The site sets it for all four files at once, so it marks the last site update, not when a particular file changed.

## Current: files as published 12 Nov 2026, 22:38 UTC

Retrieved 13 Nov 2026. This example is tested with these exact files.

| File | Address | sha256 | Last-Modified |
|---|---|---|---|
| accounts.yaml | https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/accounts/accounts.yaml | `d6370f663f53973dfc52d931333bdc350dc39f6c2680998a9054030668b4820f` | Thu, 12 Nov 2026 22:38:48 GMT |
| transactions.yaml | https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transactions/transactions.yaml | `9662089e4943dea29e8d109419388bb971301890f0ca07a4a2eff55cee19fe8d` | Thu, 12 Nov 2026 22:38:48 GMT |
| loans.yaml | https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/loans/loans.yaml | `2631ee0b97790009624ca3f9c8d233855d0ecf06556a8f0134770a831801c914` | Thu, 12 Nov 2026 22:38:48 GMT |
| transfers.yaml | https://jackhenry.dev/digital-core-api-docs/symitar-in-platform/api-reference/v1/transfers/transfers.yaml | `bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95` | Thu, 12 Nov 2026 22:38:48 GMT |

## Earlier versions

| Version | accounts.yaml | transactions.yaml | loans.yaml | transfers.yaml | Used here |
|---|---|---|---|---|---|
| Accounts as published 12 Nov 2026, 19:31 UTC | `bc18c382889a9de6f2d244e033d223981bfb77ceb85cbfee96cb603354a53399` | `c1659b038b1d7bd9c89a63ad2e688a27d89cbc1d18477627d9e0105d87f10d96` | `050962d37b56c1a35eddb7795b3fa9e4c1c6db10b01f4f5b2b46a9f4537092a5` | `bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95` | 12 Nov 2026, 21:24 UTC, until this version |
| First version this example used | `ea8fa652705d2c5531f3dcea4d18c5797797423e8a51a4a2a0403f471615228f` | `c1659b038b1d7bd9c89a63ad2e688a27d89cbc1d18477627d9e0105d87f10d96` | `050962d37b56c1a35eddb7795b3fa9e4c1c6db10b01f4f5b2b46a9f4537092a5` | `bd5ec66744b21cb3632d37e2cbdb53bbf7f3bd79cb7047cafafa9caca186de95` | 12 Nov 2026, 03:13 UTC, until 21:24 UTC |

What changed between versions is in [CHANGELOG.md](CHANGELOG.md).

## If you download newer files

At start, the example compares your files with the hashes above. If they differ, it does not stop straight away. It checks exactly what it uses, as listed in `USED` in `contract_inputs.py`:

- the six operations and their addresses;
- each request field it sends, with its type, and the required fields around it;
- each field it reads from a successful (200) reply, with its type.

If none of that changed, it starts and prints: "Your Jack Henry files differ from the ones this example was tested with (…); everything this example uses is unchanged." If any of it changed, it stops and names the operation and field. Then this example needs an update: please open an issue.
