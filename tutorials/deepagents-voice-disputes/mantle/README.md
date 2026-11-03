# Mantle voice conversation

<!-- codespaces:start -->
[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/RasaHQ/rasa-community-resources?ref=main&devcontainer_path=.devcontainer/tutorials-deepagents-voice-disputes-mantle/devcontainer.json)

- **You need:** the free Rasa Developer Edition license and the keys it names: required `RASA_LICENSE`, `OPENAI_API_KEY`, `DEEPGRAM_API_KEY`, `RIME_API_KEY`, saved once as personal Codespaces secrets ([how](../../../README.md#run-any-resource-in-a-github-codespace)). Use this button rather than the Codespaces picker, so you get this resource's setup.
- **First command:** `make train && make inspect`. The terminal opens in this folder, and the creation log ends with `READY`.
- **You should see:** training finishes, then the Inspector starts. In a second terminal, `bash "$(git rev-parse --show-toplevel)/.devcontainer/resource-base/print-inspector-url.sh"` prints its address.
<!-- codespaces:end -->

Follow [the complete tutorial](../README.md). This project owns the conversation and confirmed demo review request. Install the worker separately; never combine the lockfiles.

**Author:** Rod Rivera
**Assessed on:** 2026-10-10
**Assessed by:** Native confirmation-gate and invoker controls
**Verified with:** Rasa Pro 3.21.0.dev5 native confirmation gate and invoker with a controlled tracker; assess speech accuracy through the configured voice channel
