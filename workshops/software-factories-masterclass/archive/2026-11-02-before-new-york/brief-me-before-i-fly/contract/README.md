# Contract check for the zeocore widget types (dev17)


`accept_contract.py` (20 tests) and `accept_contract_s5e.py` (2 tests) grade `zeo_core.contracts.ui.widgets` from the pinned dev17 wheel
(sha256 724fab71d1472aaf8968c2eea7f63f6a9698850ca169d4c84a6484f0ef6e8f40): the closed registry, event envelope, revision and supersession rules,
nullable provider time, delayed and replay labels, typed assumptions, and the per-component payload shapes with negative fixtures
(cross-component, arbitrary object, missing field, extra field, markup). The JSON schemas in the parent folder are envelope-only; this is the authoritative payload check.

Run with any Python 3.12 interpreter that has only that wheel installed (for example the worker environment of the companion example):

```bash
python accept_contract.py && python accept_contract_s5e.py
```

Known gap, pinned by a test: URLs and a bare `javascript:` scheme in text values pass this contract. The product adapter refuses `://` and markup but not a bare `javascript:`, so that string passes both layers. Cards are plain text; no script execution is claimed or possible there. If a later wheel closes the gap, `test_f1_known_gap_urls_and_a_bare_javascript_scheme_pass_the_contract` fails and must be inverted.
Offline: no key, no network.
