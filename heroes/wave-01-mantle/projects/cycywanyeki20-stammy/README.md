# Stammy speech-support practice demo

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/heroes-wave-01-mantle-projects-cycywanyeki20-stammy/devcontainer.json)

This cohort snapshot installs its own locked Rasa version; it does not track catalog upgrades.

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, saved once as personal Codespaces secrets ([how](../../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make train && make inspect`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** training finishes, then the Inspector starts. In a second terminal, `bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/print-inspector-url.sh"` prints its address.
<!-- codespaces:end -->

```text
Author:        cycywanyeki20
Assessed on:   2026-11-11
Assessed by:   Rasa Community maintainers (source integration only)
Verified with: pending upstream validation
Installation:  rasa-pro 3.20.0.dev6 (maintainer integration target)
Wave:          wave-01-mantle
```

This contribution offers text-based speech practice prompts for children and
caregivers. Its rules prohibit diagnosis and promised treatment outcomes.
It is an experimental example, not a treatment or a tested clinical service.

The original contribution did not include a dependency manifest, lock or test
receipt. The maintainer integration target uses the cohort's Rasa pin; it does not establish
which version the author used. Installation, SDK validation, training and live
conversations still need their own results. No health-outcome claim is made.

## Run the example

Provide `RASA_LICENSE` and `OPENAI_API_KEY` as environment variables. From this
folder, install the committed dependencies and start the Inspector:

```bash
uv sync --locked --python 3.12
export RASA_PRO_LICENSE="$RASA_LICENSE"
uv run --locked rasa train
uv run --locked rasa inspect
```

The OpenAI model calls use your account. No microphone or speech service is
configured; the Inspector's chat is a text path. Train after changing skills.

## Source preserved from contribution 49

The original agent and both runtime skill folders are retained. Integration
credentials keep the same model and key, using the model-group shape required
by the integration target. Bundled guidance uses the current engine name. Both `speech_support` and `view_transactions` currently contain
speech-support behaviour; the latter is not a banking tool. This integration
does not remove either copy or claim the duplicate routing has been tested.
Authorship and original commits remain attributable to
[@cycywanyeki20](https://github.com/cycywanyeki20).

## Deterministic tool checks

After installation, run `uv run --locked --no-sync python -m unittest discover -s tests -v`.
These controls exercise both contributed tool copies with the real SDK imports
and a small in-memory context. They make no provider calls and do not test
speech recognition, routing or treatment outcomes. Codespaces runs them before
reporting READY. Their passing result has not yet been observed.
