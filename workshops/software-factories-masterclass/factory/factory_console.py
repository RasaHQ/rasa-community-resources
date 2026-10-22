"""Read-only view of ONE mantle-factory-v1 run, never an executor.

sow: software-factories-masterclass-SOW-02
"""
import argparse
from datetime import datetime, timezone
import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import os
from pathlib import Path
import re
import stat
import threading

SECRET_NAMES = ('OPENAI_API_KEY', 'ANTHROPIC_API_KEY', 'DEEPGRAM_API_KEY', 'RASA_LICENSE')
MAX_ARTIFACT = 256 * 1024
PREVIEW_END = datetime(2026, 10, 22, 16, 30, tzinfo=timezone.utc)


def redact(value, environment=None):
    text = str(value)
    environment = os.environ if environment is None else environment
    for name in SECRET_NAMES:
        secret = environment.get(name, '')
        if secret:
            text = text.replace(secret, '[credential redacted]')
            for index in range(len(secret) - 7):
                text = text.replace(secret[index:index + 8], '[credential fragment redacted]')
    return re.sub(r'(?im)((?:api[_-]?key|authorization|rasa_license)\s*[=:]\s*)[^\s,;]+',
                  r'\1[credential redacted]', text)


def read_artifact(root, name):
    """No URL paths, directory listings, symlinks, special files or raw logs."""
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        return None
    path = root / name
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_ARTIFACT:
            return None
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descriptor, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
                return None
            content = stream.read(MAX_ARTIFACT + 1)
        return content.decode('utf-8') if len(content) <= MAX_ARTIFACT else None
    except (OSError, UnicodeError):
        return None


def json_artifact(root, name):
    try:
        result = json.loads(read_artifact(root, name) or '{}')
        return result if isinstance(result, dict) else {}
    except (ValueError, RecursionError):
        return {}


def snapshot(root):
    public = json_artifact(root, 'console.json')
    # These are the existing factory/collect records, never builder claims of PASS.
    decision = json_artifact(Path(root) / 'verification', 'decision.json')
    review = json_artifact(Path(root) / 'review', 'review.json')
    integration = json_artifact(root, 'integration.json')
    events = []
    for line in (read_artifact(root, 'events.jsonl') or '').splitlines()[-200:]:
        try:
            event = json.loads(line)
            if isinstance(event, dict):
                events.append({key: event[key] for key in ('stage', 'status', 'action', 'path', 'bytes', 'result_sha256', 'error_code') if key in event})
        except (ValueError, RecursionError):
            continue
    checks = decision.get('checks', [])
    checks = checks if isinstance(checks, list) else []
    return {'task': public.get('task', {}), 'prepared': public.get('prepared', []),
            'state': public.get('state', 'WAITING'), 'events': events,
            'diff': read_artifact(Path(root) / 'review', 'change.patch') or '',
            'review': {'patch_sha256': review.get('patch_sha256'), 'files_changed': review.get('files_changed', [])},
            'checks': [{key: check.get(key) for key in ('name', 'passed', 'summary')}
                       for check in checks if isinstance(check, dict)],
            'decision': {key: decision.get(key) for key in ('decision', 'reasons', 'acceptance_sha256')},
            'integration': {key: integration.get(key) for key in ('status', 'decision', 'reason', 'head') if key in integration}}


def render(state):
    def escape(value):
        return html.escape(redact(value))
    def block(value):
        return '<pre>' + escape(json.dumps(value, indent=2, ensure_ascii=False)) + '</pre>'
    checks = ''.join('<li>' + escape(check['name']) + ': <strong>' +
                     ('PASS' if check['passed'] is True else 'FAIL' if check['passed'] is False else 'NOT RUN') +
                     '</strong> ' + escape(check.get('summary') or '') + '</li>' for check in state['checks'])
    return ('''<!doctype html><html lang="en"><meta charset="utf-8"><meta http-equiv="refresh" content="2">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Mantle factory run</title>
<style>body{font:18px system-ui;background:#10202d;color:#f1f4f7;max-width:1100px;margin:2em auto;padding:0 1em}
section{background:#193342;padding:1em;margin:1em 0;border-radius:8px}pre{white-space:pre-wrap;overflow-wrap:anywhere}h1,h2{line-height:1.2}</style>
<h1>The factory builds the fourth briefing card</h1><p>Read-only run evidence. Builder steps are not acceptance.</p>'''
            + '<p>Run state: ' + escape(state['state']) + '</p>'
            + '<section><h2>Task</h2>' + block(state['task']) + '</section>'
            + '<section><h2>Prepared platform</h2>' + block(state['prepared']) + '</section>'
            + '<section><h2>Builder steps</h2>' + block(state['events']) + '</section>'
            + '<section><h2>Candidate diff</h2>' + block(state['review']) + '<pre>' + escape(state['diff']) + '</pre></section>'
            + '<section><h2>Protected gates</h2><ul>' + (checks or '<li>NOT RUN</li>') + '</ul></section>'
            + '<section><h2>Factory decision</h2>' + block(state['decision']) + '</section>'
            + '<section><h2>Integration</h2>' + block(state['integration'] or {'status': 'NOT RECORDED'}) + '</section>'
            + '<p>Visible to processes or devices that can reach this listener. No write or execution endpoints.</p></html>')


def server_for(root, host='127.0.0.1', port=8943, *, expires_at=None, clock=None):
    address = ipaddress.ip_address(host)
    tailnet = address in ipaddress.ip_network('100.64.0.0/10')
    if host != '127.0.0.1' and not tailnet:
        raise ValueError('Choose localhost or the explicit tailnet address, never a public or wildcard bind.')
    if expires_at is not None and expires_at.tzinfo is None:
        raise ValueError('Use a timezone-aware preview expiry.')
    if tailnet and (expires_at is None or expires_at.tzinfo is None or expires_at > PREVIEW_END):
        raise ValueError('The tailnet preview must expire by the authorized class end.')
    root = Path(root)
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise ValueError('Choose one regular factory run directory or its future path.')
    root = root.resolve()
    clock = clock or (lambda: datetime.now(timezone.utc))
    class ReadOnly(BaseHTTPRequestHandler):
        def log_message(self, *_args):
            pass  # URLs and request headers never enter logs.

        def do_GET(self):
            if expires_at is not None and clock() >= expires_at:
                self.send_error(410, 'This temporary preview has ended.')
                return
            if self.path not in ('/', '/state.json'):
                self.send_error(404)
                return
            state = snapshot(root)
            body = (redact(json.dumps(state)).encode() if self.path == '/state.json'
                    else render(state).encode())
            self.send_response(200)
            self.send_header('Content-Type', 'application/json' if self.path == '/state.json' else 'text/html; charset=utf-8')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'")
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            self.send_error(405, 'Read-only factory view.')
        do_PUT = do_POST
        do_DELETE = do_POST
        do_PATCH = do_POST
    return ThreadingHTTPServer((host, port), ReadOnly)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_directory')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8943)
    parser.add_argument('--expires-at', help='Aware ISO timestamp; required for the tailnet preview.')
    args = parser.parse_args(argv)
    try:
        expiry = datetime.fromisoformat(args.expires_at.replace('Z', '+00:00')) if args.expires_at else None
        if expiry is not None and (expiry.tzinfo is None or expiry <= datetime.now(timezone.utc)):
            raise ValueError('Use a future, timezone-aware preview expiry.')
        server = server_for(args.run_directory, args.host, args.port, expires_at=expiry)
        if expiry is not None:
            timer = threading.Timer((expiry - datetime.now(timezone.utc)).total_seconds(), server.shutdown)
            timer.daemon = True
            timer.start()
        print('Factory console is read-only on port ' + str(args.port) + '.', flush=True)
        try:
            server.serve_forever()
        finally:
            server.server_close()
        return 0
    except (OSError, ValueError):
        print('The factory console could not start; check the run directory, bind address and preview expiry.')
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
