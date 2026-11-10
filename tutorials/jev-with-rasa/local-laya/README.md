# One pinned local decision model

Laya is an open-weight decision model by Convai Innovations, distributed under
Apache-2.0. This project serves one English checkpoint through the account Choice
question used by the Jacaranda conversation. It is a narrow application adapter,
not an implementation of every TypeSafe endpoint or question type.

Use Python 3.12 and uv. From this directory:

```sh
uv sync --locked
.venv/bin/python serve_local.py --cache-dir ./model-cache
```

The first start downloads only the five English checkpoint artifacts listed in
`model-manifest.json`, about 846 MB of logical file data. It verifies every SHA-256
before loading. The manifest pins the Hugging Face revision; `uv.lock` pins the
runtime. Reuse that one cache, and exclude it and `.venv` from copies and backups.
Neither a TypeSafe API key nor a Hugging Face account is required for this public
checkpoint. The model cache remains local and is not part of this repository.

The adapter downloads exactly the five manifest paths, checks each file's size
and SHA-256 itself, sets `HF_HUB_OFFLINE=1`, and passes that verified local
snapshot directory to Laya. A mismatch refuses startup before inference.

The recorded local run uses macOS on Apple Silicon with CPU inference. The
current cross-platform lock can install CUDA dependency wheels on Linux even
for this CPU example. Qualify a separate CPU-only Linux lock before allocating
a Linux runtime; those extra wheels are not needed by the recorded macOS run.

The server uses two CPU threads, eager PyTorch inference and loopback port 5031.
It loads once and runs until Ctrl-C. It accepts this example's single account
Choice question with up to twenty candidates. It does not generate reply prose.
The default Mantle environment does not install PyTorch or Laya; keep model
dependencies isolated from the conversation project.

Follow [the full walkthrough](../README.md) to start `make worker-local` from
`mantle`, or run `make demo-local` with this server already running. Mantle still
needs its issued licence and configured writer-provider key for conversations.

Interpret model confidence using its own implementation and qualification.
The application uses no confidence cutoff to authorise a read. It asks for
confirmation of a named proposal and checks current eligibility again.
The runtime logs shipped-temperature warnings while loading. Retain them with
the model identity when assessing scores on your own task.

Sources: [Laya code](https://github.com/NandhaKishorM/laya),
[pinned model repository](https://huggingface.co/convaiinnovations/laya/tree/7b928d828b7b0e022f929d9bd2e44165aa270148),
and [PyPI runtime](https://pypi.org/project/laya/0.4.3/).
