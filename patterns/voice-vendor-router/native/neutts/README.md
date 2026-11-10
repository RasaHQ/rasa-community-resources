# NeuTTS on Metal, without Python

The Python `neutts` package cannot be installed next to rasa-pro: it needs a
newer numpy than rasa-pro allows, and it pulls in torch. NeuTTS itself does
not need either. Its GGUF backbone runs on llama.cpp and its decoder is an
ONNX graph, so a Mac can run the whole thing natively:

```text
text ──▶ llama-server (Neuphonic's llama.cpp fork, Metal)
            neutts-2e-Q4_0.gguf  →  <|speech_N|> codes, 50 a second
     ──▶ neucodec_decoder (C++, ONNX Runtime 1.24.1, CPU)
            NeuCodec int8 decoder  →  24 kHz 16-bit audio
```

This folder builds both programs from pinned sources and puts the model
files in place with their digests checked.
[`voicerouter.providers.neutts_native.NeuTTSNative`](../../voicerouter/providers/neutts_native.py)
is the Rasa engine that drives them: it starts both once per Rasa process,
keeps them loaded, streams codes from the server and decodes them in chunks
while generation is still running. It uses `array` and `struct`, not numpy.

Tested on an Apple M4 Pro (64 GB), macOS 26.6.2, Apple clang 21, on
2026-09-30. Apple silicon only: the build refuses anything else.

## Build

```bash
./build.sh                                  # about a minute on an M4 Pro
python3 prepare_models.py --from ~/models   # files you already have, or:
HF_TOKEN=... python3 prepare_models.py --fetch
python3 prepare_models.py --check
```

`build.sh` needs git, cmake and Xcode's command-line tools. It:

1. clones `neuphonic/llama.cpp` and checks out `ff569ec0ef46…` (refused if
   HEAD differs or the tree is modified), then builds `llama-server` and
   `llama-completion` with Metal on, static libraries, the Metal shaders
   embedded, no web UI and no OpenSSL;
2. downloads the ONNX Runtime 1.24.1 macOS arm64 archive and refuses it
   unless its SHA-256 is the one GitHub lists for the release asset;
3. compiles `neucodec_decoder.cpp` against it;
4. copies or downloads (digest-checked) the licences of llama.cpp, ONNX
   Runtime, NeuTTS and NeuCodec into `build/licenses/`;
5. refuses a binary that links a Homebrew or `/usr/local` library, a
   `llama-server` without Metal, or a decoder that does not report ONNX
   Runtime 1.24.1, and writes `build/BUILD-INFO.json` with each binary's
   SHA-256.

Every pin is in [`DEPENDENCIES.lock`](DEPENDENCIES.lock); every model file's
repository, revision, size and SHA-256 is in [`models.lock`](models.lock).

`prepare_models.py` (standard library only) never downloads a file it has
not been told the digest of. The two Hugging Face repositories are gated:
accept the terms on each model page before `--fetch`. The speaker comes from
the public NeuTTS repository: `samples/sophie.pt` is a torch archive of 175
NeuCodec codes, read with `zipfile` and `struct` (the pickle is
disassembled, never executed) and checked against the digest in
`models.lock`.

## Run it by hand

```bash
M=models B=build/bin
$B/llama-server -m $M/neutts-2e-Q4_0.gguf -c 2048 -ngl 99 -np 1 \
  --special --no-ui --offline --cache-ram 0 --host 127.0.0.1 --port 8089
```

`--cache-ram 0` turns off the host-memory prompt cache. NeuTTS prompts
never repeat (the text comes before the speaker codes), so the cache is
never used, and at its default 8 GiB limit it grew the server to 3.3 GB over
one 23-call run; with the flag it stayed at 509 MB over 60 syntheses.

`--special` matters: speech codes are special tokens, and without it the
server returns an empty string for each of them. The prompt is NeuTTS-2E's:

```text
<|TEXT_PROMPT_START|>{speaker text} {your text}<|TEXT_PROMPT_END|><|SPEECH_GENERATION_START|>{speaker codes as <|speech_N|>}
```

POST it to `/completion` with `"stop": ["<|SPEECH_GENERATION_END|>"]`,
collect the `<|speech_N|>` numbers, and decode them:

```bash
$B/neucodec_decoder $M/model.onnx --codes codes.txt --wav out.wav
```

`neucodec_decoder --serve` keeps the decoder loaded and answers binary
requests on stdin and stdout; the protocol is at the top of
[`neucodec_decoder.cpp`](neucodec_decoder.cpp).

## Checked against another build

With the same prompt and seed, this build's `llama-completion`, its
`llama-server`, and an independently built `llama-completion` from the same
pinned commit produced the same 375 speech codes, and this decoder and the
other build's decoder produced byte-identical audio from them (179,520
samples, 7.48 s at 24 kHz).

## Measured on the M4 Pro

| | |
|---|---|
| Startup (digest check, server load, decoder load) | 0.74 s, once per Rasa process |
| Backbone generation, one-shot | 258 to 330 codes a second (5 to 6.6 times real time) |
| Backbone generation, streamed to the engine | 227 to 271 codes a second |
| Prompt evaluation | 210 tokens in 48 ms |
| First audio from the engine, warm | 0.18 to 0.26 s (6 utterances of 31 to 143 characters) |
| Real-time factor of the engine, whole utterance | 0.19 to 0.24 |
| Decoding 375 codes, one shot, including loading the model | 0.33 s |
| Live calls through Rasa: first audio, p50 (p95) | 195 ms (218), 97 syntheses |
| Live calls through Rasa: real-time factor, p50 (p95) | 0.174 (0.202) |
| `llama-server` memory with `--cache-ram 0`, 60 syntheses | 509 MB, flat |

Per-turn figures from live calls are in the case build that uses it,
[`mantle-voice-healthcare-refill-request-gpt-local`](../../../../examples/mantle-voice-healthcare-refill-request-gpt-local/).

## What it does not do

- **No watermark.** NeuTTS's Python package adds a Perth implicit watermark
  when `resemble-perth` is installed. This runtime does not.
- **The decoder runs on the CPU.** ONNX Runtime's CPU provider, 4 threads.
  Only the backbone uses the GPU.
- **One speaker at a time.** The engine serialises decoder calls and runs one
  server slot, so two calls speaking at the same moment wait for each other.
- **English only.** NeuTTS-2E is an English model with four fixed speakers.

## Licences

| Component | Licence | Source |
|---|---|---|
| `neutts-2e-Q4_0.gguf` backbone | `license: other` on its Hugging Face card; the NeuTTS repository's licence is the NeuTTS Open License v1.0, which allows research use and commercial use by organisations under 5 million USD annual revenue, and requires a paid licence above that | Hugging Face API for `neuphonic/neutts-2e-q4-gguf` (the card body and the repository's own LICENSE file are behind the gate and were not read); `neuphonic/neutts` LICENSE at `ac69851` |
| NeuCodec int8 ONNX decoder | Apache 2.0 | Hugging Face API for `neuphonic/neucodec-onnx-decoder-int8` (card body gated, not read) |
| Speaker `sophie` (codes and text) | Part of the NeuTTS repository, under its licence | `neuphonic/neutts` at `ac69851` |
| llama.cpp (Neuphonic fork) | MIT | `build/licenses/llama.cpp-LICENSE` |
| ONNX Runtime | MIT, with third-party notices | `build/licenses/` |
| This folder's scripts and decoder | Apache 2.0, like the rest of the repository | |
