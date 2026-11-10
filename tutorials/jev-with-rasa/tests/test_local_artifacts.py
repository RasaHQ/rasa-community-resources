"""Application-owned model verification and malformed loopback input controls."""
import hashlib
import importlib.util
import json
from http.server import HTTPServer
from pathlib import Path
import tempfile
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen
import unittest
from unittest.mock import Mock

path = Path(__file__).resolve().parents[1] / 'local-laya/serve_local.py'
spec = importlib.util.spec_from_file_location('local_laya_adapter', path)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class LocalArtifacts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / 'snapshot'
        self.manifest = {**adapter.MANIFEST, 'files': {}}
        for relative in adapter.MANIFEST['files']:
            file = self.root / relative
            file.parent.mkdir(parents=True, exist_ok=True)
            raw = relative.encode()
            file.write_bytes(raw)
            self.manifest['files'][relative] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.calls = []
        def download(**kwargs):
            self.calls.append(kwargs)
            return str(self.root / kwargs['filename'])
        self.download = download

    def tearDown(self):
        self.temp.cleanup()

    def test_only_five_pinned_paths_are_verified(self):
        self.assertEqual(adapter.verified_snapshot(self.download, self.root, self.manifest), self.root)
        self.assertEqual([x['filename'] for x in self.calls], list(adapter.MANIFEST['files']))
        self.assertEqual(len(self.calls), 5)
        for call in self.calls:
            self.assertEqual(call['revision'], adapter.MANIFEST['revision'])
            self.assertEqual(call['repo_id'], adapter.MANIFEST['repository'])
            self.assertIs(call['token'], False)

    def test_same_size_tampering_refuses_snapshot(self):
        file = self.root / 'model.safetensors'
        raw = file.read_bytes()
        file.write_bytes(b'X' + raw[1:])
        with self.assertRaisesRegex(ValueError, 'verification failed: model.safetensors'):
            adapter.verified_snapshot(self.download, self.root, self.manifest)

    def test_changed_size_refuses_snapshot(self):
        with (self.root / 'model.safetensors').open('ab') as stream:
            stream.write(b'changed')
        with self.assertRaisesRegex(ValueError, 'verification failed'):
            adapter.verified_snapshot(self.download, self.root, self.manifest)

    def test_malformed_body_and_question_return_400_before_inference(self):
        agent = Mock()
        server = HTTPServer(('127.0.0.1', 0), adapter.make_handler(agent))
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            for body in [[], {'model': adapter.MODEL_ID, 'questions': {'account': []}, 'state': {}}]:
                with self.subTest(body=body):
                    request = Request(f'http://127.0.0.1:{server.server_port}/v1/systemone',
                                      data=json.dumps(body).encode(), headers={'Content-Type': 'application/json'})
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(request, timeout=3)
                    self.assertEqual(caught.exception.code, 400)
                    caught.exception.close()
            agent.predict.assert_not_called()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)
