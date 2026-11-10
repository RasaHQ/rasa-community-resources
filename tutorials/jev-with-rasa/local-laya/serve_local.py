"""A small public-interface Laya server, isolated from the Mantle environment."""
import argparse
import hashlib
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

MANIFEST = json.loads(Path(__file__).with_name("model-manifest.json").read_text())
MODEL_ID = "laya-en@" + MANIFEST["revision"]


def verified_snapshot(download, cache_dir, manifest=MANIFEST):
    """Fetch only manifest paths and check bytes ourselves before model loading."""
    root = None
    for relative, expected in manifest["files"].items():
        file = Path(download(repo_id=manifest["repository"], filename=relative,
                             revision=manifest["revision"], cache_dir=str(cache_dir), token=False))
        candidate_root = file.parents[len(Path(relative).parts) - 1]
        if root is not None and candidate_root != root:
            raise ValueError("Model artifacts must share one pinned snapshot directory")
        root = candidate_root
        digest = hashlib.sha256()
        with file.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if file.stat().st_size != expected["bytes"] or digest.hexdigest() != expected["sha256"]:
            raise ValueError(f"Model artifact verification failed: {relative}")
    if root is None:
        raise ValueError("Model manifest is empty")
    return root


def make_handler(agent):
    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            if self.path != "/v1/systemone":
                self.send_error(404)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 16000:
                    raise ValueError()
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict) or body.get("model") != MODEL_ID:
                    raise ValueError()
                questions = body.get("questions")
                if not isinstance(questions, dict) or set(questions) != {"account"}:
                    raise ValueError()
                q = questions["account"]
                if not isinstance(q, dict) or not isinstance(q.get("criteria"), dict):
                    raise ValueError()
                if q.get("type") != "choice" or not 1 <= len(q["criteria"]) <= 20:
                    raise ValueError()
                result = agent.predict(body["state"], questions)
                reply = {"model": MODEL_ID, "answers": result["answers"], "usage": result["usage"]}
            except (ValueError, TypeError, KeyError):
                self.send_error(400)
                return
            raw = json.dumps(reply, allow_nan=False).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, *_):
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cache-dir", type=Path, required=True, help="Dedicated model cache, not another seat's root")
    parser.add_argument("--port", type=int, default=5031)
    args = parser.parse_args()
    # Set before importing the model runtime. Never download sibling checkpoints.
    os.environ["HF_HUB_CACHE"] = str(args.cache_dir.resolve())
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["HF_XET_CACHE"] = str(args.cache_dir.resolve() / "xet")
    os.environ["HF_XET_CHUNK_CACHE_SIZE_BYTES"] = "0"
    os.environ["USE_TF"] = "0"
    from huggingface_hub import hf_hub_download
    snapshot = verified_snapshot(hf_hub_download, args.cache_dir.resolve())
    os.environ["HF_HUB_OFFLINE"] = "1"
    import torch
    import laya
    torch.set_num_threads(2)
    agent = laya.load(str(snapshot), device="cpu", backend="eager")
    with HTTPServer(("127.0.0.1", args.port), make_handler(agent)) as server:
        print("Local Laya ready; model=" + MODEL_ID, flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
