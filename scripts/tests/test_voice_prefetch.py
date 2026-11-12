"""Cache pin/refusal controls; no model library, download or provider is used."""
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("prefetch", Path(__file__).resolve().parents[1] / "prefetch_voice_model.py")
v = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(v)


class CacheControls(unittest.TestCase):
    def test_unsupported_sdk_refuses_before_any_download(self):
        calls = []
        with self.assertRaises(ValueError):
            v.prepare(True, sdk_version="3.22.0.dev3", downloader=lambda *a, **k: calls.append(a))
        self.assertEqual(calls, [])

    def test_wrong_main_revision_stops_before_large_model_download(self):
        calls = []
        def download(repo, name, **kw):
            calls.append(name)
            return "/cache/snapshots/changed-revision/" + name
        with self.assertRaises(ValueError):
            v.prepare(True, sdk_version=v.SDK, downloader=download)
        self.assertEqual(calls, ["tokenizer.json"])

    def test_cache_check_never_authorizes_network_and_checks_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "snapshots" / v.REVISION / "tokenizer.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"authored-control")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            calls = []
            def download(repo, name, **kw):
                calls.append((repo, name, kw))
                return str(path)
            with patch.object(v, "FILES", {"tokenizer.json": (16, digest)}):
                result = v.prepare(sdk_version=v.SDK, downloader=download)
                self.assertEqual(result["status"], "verified_cache")
                self.assertEqual(calls[0][2], {"revision": "main", "local_files_only": True})
                path.write_bytes(b"tampered-control")
                with self.assertRaises(ValueError):
                    v.prepare(sdk_version=v.SDK, downloader=download)

    def test_truncated_model_is_not_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "partial.onnx"
            path.write_bytes(b"short")
            with self.assertRaises(ValueError):
                v.verify_file(path, 10, hashlib.sha256(b"short").hexdigest())


if __name__ == "__main__":
    unittest.main()
