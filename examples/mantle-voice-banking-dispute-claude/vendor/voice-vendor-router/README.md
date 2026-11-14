# Vendored voice vendor router

A copy of [`patterns/voice-vendor-router`](../../../../patterns/voice-vendor-router/)
from commit `730b61da7adbbd4b212718e0d40c00490fd6c201`, kept inside this example so the
example installs, imports and runs from its own folder. Keep in sync: when the
pattern changes, copy the same files again and update the commit above.

The example's `pyproject.toml` installs this folder as the `voice-vendor-router`
package (an editable path source), so engine names such as
`voicerouter.RoutedASR` and `voicerouter.providers.speechmatics.SpeechmaticsASR`
resolve exactly as they do for the pattern.

What is here:

- `voicerouter/`: the package, unchanged.
- `tests/`: the pattern's offline router tests, unchanged. Run them from the
  example folder with `make router-test`. Two pattern tests are left out
  because they read files outside this copy: `test_bench.py` (the pattern's
  benchmark script and audio fixtures) and `test_shared_profile.py` (a
  tutorial's shared speech code).
- `.env.example`: the pattern's credential list, read by `tests/test_voicerouter.py`.
  The example's own `.env.example` is the one to copy.
- `native/neutts/`: the native NeuTTS-2E build files (llama.cpp on Metal plus a
  C++ NeuCodec decoder), unchanged. This example does not use
  `NeuTTSNative`; the files are here because the engine reads
  `native/neutts/models.lock` next to the package, and its tests check that.
  Run `native/neutts/build.sh` from this folder only if you switch to it.
- `pyproject.toml`: the pattern's package metadata without its Rasa
  development group (see the comment at its top).

The pattern's [README](../../../../patterns/voice-vendor-router/README.md)
explains the router.
