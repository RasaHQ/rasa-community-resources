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
    fallback = public.get('integration')
    if (isinstance(fallback, dict) and fallback.get('status') == 'FAILED'
            and fallback.get('reason_code') == 'integration_record_write_failed'):
        integration = fallback
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
            'state': public.get('state', 'WAITING'), 'mode': public.get('mode', 'UNSPECIFIED'), 'events': events,
            'diff': read_artifact(Path(root) / 'review', 'change.patch') or '',
            'review': {'patch_sha256': review.get('patch_sha256'), 'files_changed': review.get('files_changed', [])},
            'checks': [{key: check.get(key) for key in ('name', 'passed', 'summary')}
                       for check in checks if isinstance(check, dict)],
            'decision': {key: decision.get(key) for key in ('decision', 'reasons', 'acceptance_sha256')},
            'integration': {key: integration.get(key) for key in
                            ('status', 'decision', 'reason', 'head', 'reason_code', 'candidate_digest',
                             'baseline_head', 'integrated_head', 'receipt_ref') if key in integration}}


# Supplied Rasa brand tokens v0.2.0: semantic web palette and font stacks.
# No font binaries, web-font request, logo redraw or new framework is included.
CONSOLE_CSS = """
:root{--rasa-bg:#FAF6F0;--rasa-panel:#FFFBF5;--rasa-subtle:#F3EEE7;--rasa-muted:#EDE8E0;
--rasa-ink:#181210;--rasa-muted-ink:#524A43;--rasa-border:#C8C0B6;--rasa-link:#AA1E54;
--rasa-success:#C6FEE1;--rasa-success-ink:#2B5E47;--rasa-error:#FEF5F8;
font-family:"STK Bureau Sans",Inter,Arial,sans-serif;color:var(--rasa-ink);background:var(--rasa-bg);font-synthesis:none}
*{box-sizing:border-box}body{margin:0;font-size:18px;line-height:1.6}main{max-width:1440px;margin:auto;padding:48px 56px}
h1,h2{font-family:"STK Bureau Serif",Newsreader,Georgia,serif;font-weight:400;line-height:1.12;letter-spacing:-.02em}
h1{font-size:clamp(34px,4vw,60px);max-width:980px;margin:16px 0 24px}h2{font-size:32px;margin:0 0 16px}
p{max-width:820px}a{color:var(--rasa-link);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid var(--rasa-link);outline-offset:4px}
.eyebrow{font-family:"STK Bureau Sans Mono","JetBrains Mono",ui-monospace,monospace;font-size:13px;text-transform:uppercase;letter-spacing:.06em}
.lead{font-size:20px}.muted{color:var(--rasa-muted-ink)}section{border-top:1px solid var(--rasa-border);padding:32px 0;min-width:0;overflow-wrap:anywhere}
.flow{list-style:none;padding:24px;margin:32px 0;background:var(--rasa-muted);border-radius:16px;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:20px}
.flow li{position:relative}.flow strong,.flow span{display:block}.flow span{font-size:15px;color:var(--rasa-muted-ink)}.flow li:not(:last-child):after{content:"→";position:absolute;right:-16px;top:0;color:var(--rasa-link)}
.chip{display:inline-block;padding:4px 12px;border-radius:4px;background:var(--rasa-subtle);color:var(--rasa-muted-ink);font-size:15px;font-weight:600}
.pass{background:var(--rasa-success);color:var(--rasa-success-ink)}.fail{background:var(--rasa-error);color:var(--rasa-link);border:1px solid var(--rasa-link)}
.steps{padding-left:24px;max-height:360px;overflow:auto}.steps li{margin:12px 0}.path{overflow-wrap:anywhere;font-family:ui-monospace,monospace;font-size:14px}
pre{max-width:100%;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;background:var(--rasa-panel);padding:20px;border:1px solid var(--rasa-border);border-radius:12px;font:14px/1.6 "STK Bureau Sans Mono","JetBrains Mono",ui-monospace,monospace}
summary{cursor:pointer;color:var(--rasa-link);padding:12px 0}footer{border-top:1px solid var(--rasa-border);padding:24px 0;font-size:14px}
@media(max-width:991px){main{padding:32px}.flow{grid-template-columns:1fr;gap:24px}.flow li:not(:last-child):after{content:"↓";right:auto;top:auto;bottom:-26px;left:0}.flow li{padding-left:24px}}
@media(max-width:767px){main{padding:24px 20px}h2{font-size:28px}.lead{font-size:18px}}
@media(prefers-reduced-motion:reduce){*{scroll-behavior:auto}}
"""


def render(state, *, refresh=True):
    def escape(value):
        return html.escape(redact(value))
    def block(value):
        return '<pre>' + escape(json.dumps(value, indent=2, ensure_ascii=False)) + '</pre>'
    def chip(label, passed=None):
        style = 'pass' if passed is True else 'fail' if passed is False else ''
        return '<span class="chip ' + style + '">' + escape(label) + '</span>'
    task = state['task'] if isinstance(state['task'], dict) else {}
    request = task.get('request') or 'The written task will appear here when the run starts.'
    actions = {'session_started': 'Started the builder session', 'session_finished': 'Finished the builder session',
               'list_files': 'Listed available files', 'read_file': 'Read a file', 'write_file': 'Changed a file',
               'run_failed': 'The run could not continue'}
    steps = ''
    for event in state['events']:
        text = actions.get(event.get('action')) or {
            'collect': 'Collected the proposed change', 'verification': 'Ran the independent checks',
            'decision': 'Recorded the checks’ decision', 'integration': 'Updated the assistant'}.get(event.get('stage'), 'Recorded a step')
        steps += '<li>' + escape(text) + ' ' + chip(event.get('status', 'RECORDED'),
                    True if event.get('status') in ('PASS', 'ACCEPT') else False if event.get('status') in ('FAIL', 'REJECT') else None)
        if event.get('path'):
            steps += '<div class="path">' + escape(event['path']) + '</div>'
        steps += '</li>'
    checks = ''
    for check in state['checks']:
        if check['name'] == "builder's own tests (informational)":
            continue
        label = 'PASS' if check['passed'] is True else 'FAIL' if check['passed'] is False else 'NOT RUN'
        checks += '<li>' + escape(check['name']) + ' ' + chip(label, check['passed'])
        if check.get('summary'):
            checks += '<div class="path">' + escape(check['summary']) + '</div>'
        checks += '</li>'
    examples = ''
    for example in state.get('comparisons', []):
        verdict = example['decision'].get('decision')
        examples += '<li><strong>' + escape(example['label']) + '</strong> ' + chip(verdict or 'NOT DECIDED',
                    True if verdict == 'ACCEPT' else False if verdict == 'REJECT' else None)
        examples += '<ul>' + ''.join('<li>' + escape(reason) + '</li>' for reason in (example['decision'].get('reasons') or [])) + '</ul></li>'
    comparison_section = ('<section><h2>Compare the checked teaching attempts</h2><p>These are separate offline teaching attempts, '
                          'checked by the real protected gates. They are not model results.</p><ul>' + examples + '</ul></section>') if examples else ''
    decision = state['decision'].get('decision')
    verdict = ('The change meets the written checks.' if decision == 'ACCEPT' else
               'The change did not meet the written checks; the assistant stays unchanged.' if decision == 'REJECT' else
               'The independent checks have not accepted a change.')
    integration = state['integration']
    state_words = {'WAITING': 'Waiting for a run', 'BUILDER_RUNNING': 'The builder is working',
                   'ACCEPT': 'Checks accepted the change', 'REJECT': 'Checks rejected the change',
                   'ERROR': 'The run needs attention', 'NOT_READY': 'The runtime is not ready',
                   'NO_CANDIDATE': 'No change was produced', 'BUILDER_INCOMPLETE': 'The builder stopped before completion'}
    refresh_tag = '<meta http-equiv="refresh" content="2">' if refresh else ''
    toggle = '<a href="/paused">Pause automatic refresh to read the details</a>' if refresh else '<a href="/">Resume automatic refresh</a>'
    mode_label = ('SCRIPTED control — no model request' if state.get('mode') == 'SCRIPTED' else
                  'Managed API run — see the recorded outcome' if state.get('mode') == 'LIVE_NATIVE' else 'Run mode not recorded')
    return ('<!doctype html><html lang="en"><meta charset="utf-8">' + refresh_tag
        + '<meta name="viewport" content="width=device-width,initial-scale=1"><title>Build a checked change · Rasa workshop</title>'
        + '<style>' + CONSOLE_CSS + '</style><main><header><p class="eyebrow">Rasa · Software factory workshop</p>'
        + '<h1>Build the market card, one checked step at a time</h1>'
        + '<p class="lead">A software factory is a repeatable path from a written task to a tested change. '
        + 'Here, the change adds a currency panel to the travel assistant. An AI model is a service that proposes changes from instructions.</p>'
        + '<p class="muted">The workshop builds these parts one at a time. This page shows what each part does and the evidence it records.</p>'
        + '<ol class="flow" aria-label="From a task to a checked change">'
        + '<li><strong>1. Write the task</strong><span>Say what must change.</span></li>'
        + '<li><strong>2. Build a change</strong><span>The model edits a copy.</span></li>'
        + '<li><strong>3. Run the checks</strong><span>Separate tests judge it.</span></li>'
        + '<li><strong>4. Accept or reject</strong><span>Record why it passed or failed.</span></li>'
        + '<li><strong>5. Update the assistant</strong><span>Use only the accepted change.</span></li></ol>'
        + chip(mode_label) + ' ' + chip(state_words.get(state['state'], 'Run state recorded')) + '<p>' + toggle + '</p></header>'
        + '<section id="task"><h2>Start with a written task</h2><p>' + escape(request) + '</p>'
        + '<details><summary>See which files may change</summary>' + block(task.get('allowed_paths', [])) + '</details></section>'
        + '<section><h2>Reuse the prepared components</h2><p>Prepared components are the parts already available before this change starts.</p>'
        + '<ul>' + ''.join('<li>' + escape(item) + '</li>' for item in (state['prepared'] if isinstance(state['prepared'], list) else [])) + '</ul></section>'
        + '<section><h2>Watch the builder’s file actions</h2><p>The builder is a model that asks tools to read or edit its working copy. '
        + 'These file actions are progress, not proof that the result is correct.</p><ol class="steps">'
        + (steps or '<li>No builder action has been recorded yet.</li>') + '</ol></section>'
        + '<section><h2>Inspect the proposed change</h2><p>A diff shows the lines added or removed. It does not decide whether they are correct.</p><pre>'
        + escape(state['diff'] or 'The diff will appear after the files are collected.') + '</pre>'
        + '<details><summary>See the change’s verification record</summary>' + block(state['review']) + '</details></section>'
        + '<section><h2>Let separate checks judge the change</h2><p>These tests are kept outside the builder’s copy. '
        + 'They check the written requirements after the builder has stopped.</p><ul>'
        + (checks or '<li>' + chip('NOT RUN') + '</li>') + '</ul></section>'
        + '<section><h2>Make the decision visible</h2>' + chip(decision or 'NOT DECIDED', True if decision == 'ACCEPT' else False if decision == 'REJECT' else None)
        + '<p>' + verdict + '</p><ul>' + ''.join('<li>' + escape(reason) + '</li>' for reason in (state['decision'].get('reasons') or [])) + '</ul></section>'
        + comparison_section
        + '<section><h2>Update the running assistant only after acceptance</h2><p>Acceptance permits integration: applying exactly the checked change. '
        + 'A rejected change must leave the running assistant untouched.</p>' + block(integration or {'status': 'NOT RECORDED'}) + '</section>'
        + '<footer>Read-only evidence view. Devices or local processes that can reach this listener can read it. '
        + 'This page cannot run a builder or approve a change. Font files are not downloaded.</footer></main></html>')


def server_for(root, host='127.0.0.1', port=8943, *, expires_at=None, clock=None, comparisons=(), viewer_access=None):
    address = ipaddress.ip_address(host)
    tailnet = address in ipaddress.ip_network('100.64.0.0/10')
    if host != '127.0.0.1' and not tailnet:
        raise ValueError('Choose localhost or the explicit tailnet address, never a public or wildcard bind.')
    if expires_at is not None and expires_at.tzinfo is None:
        raise ValueError('Use a timezone-aware preview expiry.')
    if tailnet and (expires_at is None or expires_at.tzinfo is None or expires_at > PREVIEW_END):
        raise ValueError('The tailnet preview must expire by the authorized class end.')
    if tailnet and viewer_access not in ('operator-device-acl', 'operator-accepted'):
        raise ValueError('Declare the authorized preview audience; this does not enforce a device ACL.')
    if len(comparisons) > 4:
        raise ValueError('At most four explicit teaching comparisons are supported.')
    comparisons = tuple(Path(path) for path in comparisons)
    if any(path.is_symlink() or not path.is_dir() for path in comparisons):
        raise ValueError('Teaching comparisons must be explicit regular run directories.')
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
            if self.path not in ('/', '/paused', '/state.json'):
                self.send_error(404)
                return
            state = snapshot(root)
            state['comparisons'] = [{'label': path.name, 'decision': snapshot(path)['decision']} for path in comparisons]
            body = (redact(json.dumps(state)).encode() if self.path == '/state.json'
                    else render(state, refresh=self.path != '/paused').encode())
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
    parser.add_argument('--comparison-run', action='append', default=[], help='Explicit prior offline teaching run directory (at most four).')
    parser.add_argument('--viewer-access', choices=('operator-device-acl', 'operator-accepted'), help='Tailnet audience declaration; does not enforce an ACL.')
    args = parser.parse_args(argv)
    try:
        expiry = datetime.fromisoformat(args.expires_at.replace('Z', '+00:00')) if args.expires_at else None
        if expiry is not None and (expiry.tzinfo is None or expiry <= datetime.now(timezone.utc)):
            raise ValueError('Use a future, timezone-aware preview expiry.')
        server = server_for(args.run_directory, args.host, args.port, expires_at=expiry,
                            comparisons=args.comparison_run, viewer_access=args.viewer_access)
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
