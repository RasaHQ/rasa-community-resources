#!/usr/bin/env python3
"""Check or explicitly prefetch the pinned 3.21.0.dev5 voice barge-in model.

Run with the example's locked Python environment. Default mode is cache-only;
--download permits the three public model-file downloads, never provider calls.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import time

SDK = "3.21.0.dev5"
MODEL = "MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33"
REVISION = "262ae02f29173eec1c250f90804dc7edc677dcff"
FILES = {
    "tokenizer.json": (8656646, "05402ffae6dd382a8491b1d29bfc139bec5d332662e86a026f433ce54c25c202"),
    "config.json": (1017, "dc6de98193d85d4c45f96724e6dd3672b897af3f1592e02625b9a71be795887b"),
    "onnx/model_quantized.onnx": (87246195, "1fbf78872ceab4e8003eaa0696896008c019d5a239be734c5d6230f312ad480e"),
}


def verify_file(path, size, sha256):
    path = Path(path)
    if path.stat().st_size != size:
        raise ValueError("model file size mismatch")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != sha256:
        raise ValueError("model file digest mismatch")


def prepare(download=False, *, downloader=None, sdk_version=None):
    version = sdk_version if sdk_version is not None else importlib.metadata.version("rasa-pro")
    if version != SDK:
        raise ValueError("unsupported SDK; inspect its actual loader before adapting")
    if downloader is None:
        from huggingface_hub import hf_hub_download
        downloader = hf_hub_download
    started = time.monotonic()
    files = []
    for name, (size, digest) in FILES.items():
        # Match the installed SDK's main-ref lookup, not a disconnected revision
        # cache. Check the resolved revision BEFORE continuing to the large file.
        path = Path(downloader(MODEL, name, revision="main", local_files_only=not download))
        if path.parent.name == "onnx":
            snapshot = path.parent.parent
        else:
            snapshot = path.parent
        if snapshot.name != REVISION or snapshot.parent.name != "snapshots":
            raise ValueError("resolved model revision changed; no warm-cache claim")
        verify_file(path, size, digest)
        files.append({"file": name, "bytes": size, "sha256": digest})
    return {"sdk_version": version, "model": MODEL, "revision": REVISION,
            "mode": "download_allowed" if download else "cache_only",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 3),
            "files": files, "status": "verified_cache",
            "scope": "Files verified; no voice session or latency improvement implied"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", help="allow the three public model downloads")
    args = parser.parse_args()
    try:
        report = prepare(args.download)
    except Exception as error:
        # Library errors can include URLs or local configuration. Retain only
        # the type; never echo environment values or claim a successful prefetch.
        print(json.dumps({"status": "not_verified", "error_type": type(error).__name__}), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
