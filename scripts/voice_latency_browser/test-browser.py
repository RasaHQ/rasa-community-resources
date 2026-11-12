"""Optional Playwright receiving control: local fake WebSocket, zero provider calls.

Run from a tooling environment with Playwright/Chromium already installed.
"""
import argparse
import base64
import functools
import http.server
import io
import json
from pathlib import Path
import struct
import sys
import threading
import time
import wave

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--repo', type=Path, default=Path(__file__).resolve().parents[2])
parser.add_argument('--webroot', type=Path, default=Path(__file__).resolve().parent)
args = parser.parse_args()
sys.path.insert(0, str(args.repo / 'scripts/case_builds'))
from voice_driver import accept_key, encode_frame, read_frame, WebSocketClosed  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402


class Control(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *unused):
        pass

    def do_GET(self):
        if self.headers.get('Upgrade', '').lower() != 'websocket':
            return super().do_GET()
        self.send_response(101)
        self.send_header('Upgrade', 'websocket')
        self.send_header('Connection', 'Upgrade')
        self.send_header('Sec-WebSocket-Accept', accept_key(self.headers['Sec-WebSocket-Key']))
        self.end_headers()
        self.connection.settimeout(10)

        def send(row):
            self.connection.sendall(encode_frame(1, json.dumps(row).encode(), mask=False))

        send({'type': 'handshake', 'sample_rate': 16000})
        # Deliberately immediate: exercise message serialization while the
        # asynchronous AudioWorklet module is still loading.
        send({'audio': base64.b64encode(struct.pack('<h', 3276) * 1600).decode()})
        spoken = replied = False
        try:
            while True:
                _, opcode, data = read_frame(self.connection)
                if opcode == 8:
                    break
                if opcode != 1:
                    continue
                row = json.loads(data)
                if 'audio' not in row:
                    continue
                pcm = base64.b64decode(row['audio'])
                if any(pcm):
                    spoken = True
                elif spoken and not replied:
                    replied = True
                    time.sleep(.2)
                    # 500 ms silent prefix MUST remain in the render latency;
                    # measuring non-silent receive time would undercount it.
                    bot = b'\0' * 16000 + struct.pack('<h', 6553) * 1600
                    send({'audio': base64.b64encode(bot).decode()})
        except (OSError, EOFError, WebSocketClosed):
            pass
        self.close_connection = True


server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(Control, directory=str(args.webroot)))
threading.Thread(target=server.serve_forever, daemon=True).start()
url = f'http://127.0.0.1:{server.server_port}'
try:
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=['--no-sandbox', '--autoplay-policy=no-user-gesture-required'])
        try:
            page = browser.new_page()
            page.goto(url)
            page.fill('#endpoint', url.replace('http:', 'ws:') + '/websocket')
            page.click('#connect')
            page.wait_for_function("voiceTiming().received_audio && voiceTiming().queued_samples===0 && voiceTiming().quiet_ms>200", timeout=10000)
            fixture = io.BytesIO()
            with wave.open(fixture, 'wb') as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(struct.pack('<h', 3276) * 3200)
            page.set_input_files('#fixture', {'name': 'authored-control.wav', 'mimeType': 'audio/wav', 'buffer': fixture.getvalue()})
            page.click('#speak')
            page.wait_for_function("voiceTiming().events.some(x=>x.event==='audio.first_played')", timeout=10000)
            result = page.evaluate('voiceTiming()')
            page.click('#stop')
            assert result['failure'] is None, result
            assert len(result['events']) == 2, result
            delta = result['events'][1]['at_ms'] - result['events'][0]['at_ms']
            assert 650 <= delta < 1500, result
            print(json.dumps({'status': 'PASS', 'scope': 'authored local protocol control; no provider', 'render_latency_ms': delta, 'events': result['events']}))
        finally:
            browser.close()
finally:
    server.shutdown()
    server.server_close()
