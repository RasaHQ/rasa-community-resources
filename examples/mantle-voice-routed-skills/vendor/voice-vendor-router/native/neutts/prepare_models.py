#!/usr/bin/env python3
"""Put the NeuTTS-2E model pack in place and prove every byte of it.

    python3 prepare_models.py --from ~/models/neutts      # use files you already have
    HF_TOKEN=... python3 prepare_models.py --fetch        # download the gated files
    python3 prepare_models.py --check                     # verify what is in place

Standard library only. Writes to `models/` next to this file (or `--dest`):

- `neutts-2e-Q4_0.gguf` and `model.onnx`: the backbone and the NeuCodec int8
  decoder. Both Hugging Face repositories are gated: accept the terms on each
  model page with your account before `--fetch`. With `--from`, the files are
  searched for by name under the given folders (recursively), checked for size
  and SHA-256 against `models.lock`, and symlinked, not copied.
- `sophie.codes` and `sophie.txt`: NeuTTS-2E's fixed speaker "sophie", from
  the public NeuTTS repository at the pinned commit. `sophie.pt` is a torch
  zip archive holding 175 int32 NeuCodec codes; it is read with `zipfile` and
  `struct`, so no torch is needed.

Anything that does not match `models.lock` is refused (exit 65) and nothing is
left in place under its name. The token is read from the environment, sent
only as an Authorization header to huggingface.co, and never printed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pickletools
import struct
import sys
import urllib.request
import zipfile
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read_lock(path: Path) -> dict[str, str]:
    values = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            key, _, value = line.partition("=")
            values[key] = value
    return values


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 22), b""):
            digest.update(block)
    return digest.hexdigest()


def refuse(message: str) -> None:
    print(f"REFUSED: {message}", file=sys.stderr)
    raise SystemExit(65)


def verify(path: Path, size: int, sha: str) -> bool:
    return path.is_file() and path.stat().st_size == size and sha256_file(path) == sha


def fetch(url: str, target: Path, headers: dict[str, str]) -> None:
    partial = target.with_suffix(target.suffix + ".partial")
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=120) as response, partial.open("wb") as out:
        while block := response.read(1 << 20):
            out.write(block)
    partial.replace(target)


def speaker_codes_from_pt(data: bytes) -> list[int]:
    """The int32 codes in a torch-saved 1-D IntTensor, without torch."""
    archive = zipfile.ZipFile(BytesIO(data))
    names = archive.namelist()
    pkl = next(n for n in names if n.endswith("/data.pkl"))
    root = pkl[: -len("data.pkl")]
    # Refuse anything but the one shape this reader understands: a single
    # IntStorage rebuilt as a contiguous tensor. The pickle is disassembled,
    # never executed.
    listing = StringIO()
    pickletools.dis(BytesIO(archive.read(pkl)), out=listing)
    text = listing.getvalue()
    if "torch IntStorage" not in text or "_rebuild_tensor_v2" not in text:
        refuse("speaker .pt is not a single IntStorage tensor")
    if archive.read(root + "byteorder").strip() != b"little":
        refuse("speaker .pt is not little-endian")
    raw = archive.read(root + "data/0")
    return list(struct.unpack(f"<{len(raw) // 4}i", raw))


def prepare_speaker(lock: dict[str, str], dest: Path) -> dict:
    name = lock["speaker.name"]
    pt = urllib.request.urlopen(lock["speaker.pt.url"], timeout=60).read()
    if hashlib.sha256(pt).hexdigest() != lock["speaker.pt.sha256"]:
        refuse(f"{name}.pt failed SHA-256 verification")
    txt = urllib.request.urlopen(lock["speaker.txt.url"], timeout=60).read()
    if hashlib.sha256(txt).hexdigest() != lock["speaker.txt.sha256"]:
        refuse(f"{name}.txt failed SHA-256 verification")
    codes = (" ".join(str(c) for c in speaker_codes_from_pt(pt)) + "\n").encode()
    text = (txt.decode("utf-8").strip() + "\n").encode()
    if hashlib.sha256(codes).hexdigest() != lock["speaker.codes.sha256"]:
        refuse(f"{name}.codes extracted from {name}.pt does not match models.lock")
    if hashlib.sha256(text).hexdigest() != lock["speaker.text.sha256"]:
        refuse(f"{name}.txt does not match models.lock")
    (dest / f"{name}.codes").write_bytes(codes)
    (dest / f"{name}.txt").write_bytes(text)
    return {"codes": len(codes.split()), "source": lock["speaker.pt.url"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--from", dest="sources", nargs="+", type=Path, help="folders holding the files already")
    mode.add_argument("--fetch", action="store_true", help="download the gated files with HF_TOKEN")
    mode.add_argument("--check", action="store_true", help="only verify the pack in --dest")
    parser.add_argument("--dest", type=Path, default=HERE / "models")
    args = parser.parse_args()

    lock = read_lock(HERE / "models.lock")
    dest: Path = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    report: dict = {"verified_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "files": {}}

    for part in ("backbone", "decoder"):
        filename, size, sha = lock[f"{part}.file"], int(lock[f"{part}.bytes"]), lock[f"{part}.sha256"]
        target = dest / filename
        if args.check:
            if not verify(target, size, sha):
                refuse(f"{target} is missing or does not match models.lock")
        elif args.sources:
            if verify(target, size, sha):
                pass
            else:
                found = next(
                    (p for src in args.sources for p in sorted(src.expanduser().rglob(filename))
                     if verify(p, size, sha)),
                    None,
                )
                if found is None:
                    refuse(f"no {filename} of {size} bytes with SHA-256 {sha} under {args.sources}")
                if target.is_symlink() or target.exists():
                    target.unlink()
                target.symlink_to(found.resolve())
        else:
            if not verify(target, size, sha):
                token = os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")
                if not token:
                    print("HELD: the NeuTTS model repositories are gated; accept their terms on "
                          "huggingface.co and set HF_TOKEN.", file=sys.stderr)
                    return 77
                url = (f"https://huggingface.co/{lock[f'{part}.repo']}/resolve/"
                       f"{lock[f'{part}.revision']}/{filename}")
                fetch(url, target, {"Authorization": f"Bearer {token}"})
                if not verify(target, size, sha):
                    target.unlink()
                    refuse(f"downloaded {filename} failed size or SHA-256 verification")
        report["files"][filename] = {
            "repo": lock[f"{part}.repo"], "revision": lock[f"{part}.revision"],
            "bytes": size, "sha256": sha, "path": str(target.resolve()),
        }
        print(f"verified {filename} ({size} bytes, sha256 {sha[:12]}...)")

    name = lock["speaker.name"]
    if args.check:
        for suffix, key in ((".codes", "speaker.codes.sha256"), (".txt", "speaker.text.sha256")):
            path = dest / f"{name}{suffix}"
            if not path.is_file() or sha256_file(path) != lock[key]:
                refuse(f"{path} is missing or does not match models.lock")
        report["speaker"] = {"name": name}
    else:
        report["speaker"] = {"name": name, **prepare_speaker(lock, dest)}
    print(f"verified speaker {name}")
    (dest / "MODELS-VERIFIED.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"NeuTTS-2E model pack verified in {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
