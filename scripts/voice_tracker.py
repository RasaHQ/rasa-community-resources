#!/usr/bin/env python3
"""Project numeric SDK tracker timings while an authorized local server is alive.

One read-only loopback HTTP request, no retries or provider calls. Raw tracker
text, sender identities, endpoints and command arguments are never persisted.
"""
import argparse
import http.client
import json
import math
import os
from pathlib import Path
import re
import socket
import threading
import time
from urllib.parse import quote, urlsplit

MAX_BYTES = 2 * 1024 * 1024
FIELDS = {
    'server_trigger_to_first_output_ms': ('user_perceived_latency_ms',),
    'llm_before_first_output_ms': ('llm_generation_before_first_output_ms',),
    'command_generator_ms': ('command_generator_ms',),
    'llm_first_token_ms': ('first_agent_response', 'llm_time_to_first_token_ms'),
    'llm_generation_ms': ('first_agent_response', 'llm_total_generation_ms'),
    'tts_first_byte_ms': ('first_voice_response', 'tts_time_to_first_byte_ms'),
    'tts_generation_ms': ('first_voice_response', 'tts_total_generation_ms'),
    'prediction_loop_ms': ('full_turn', 'prediction_loop_ms'),
}


def project(tracker):
    if not isinstance(tracker, dict) or not isinstance(tracker.get('events'), list):
        raise ValueError('invalid tracker envelope')
    if len(tracker['events']) > 10000:
        raise ValueError('too many tracker events')
    turns = []
    for event in tracker['events']:
        if not isinstance(event, dict) or event.get('event') != 'bot_turn_ended':
            continue
        metadata = event.get('metadata')
        raw = metadata.get('latency_breakdown') if isinstance(metadata, dict) else None
        raw = raw if isinstance(raw, dict) else {}
        metrics, invalid = {}, []
        for name, path in FIELDS.items():
            value = raw
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if value is None:
                metrics[name] = None
            elif type(value) in (int, float) and math.isfinite(value) and value >= 0:
                metrics[name] = value
            else:
                metrics[name] = None
                invalid.append(name)
        turns.append({'server_turn_ordinal': len(turns) + 1, 'metrics': metrics, 'invalid_metrics': invalid})
    return {'schema': 'rasa.voice-latency-server-projection/v1', 'status': ('collected' if any(value is not None for turn in turns for value in turn['metrics'].values()) else 'no_phase_values'), 'turns': turns,
            'scope': 'SDK numeric metadata; server trigger/output is not browser speech/playback',
            'browser_clock_join': 'not_established', 'asr_final': 'not_collected', 'mcp_calls': 'not_collected'}


def fetch(base_url, conversation_id, timeout):
    parsed = urlsplit(base_url)
    if (parsed.scheme != 'http' or parsed.hostname not in ('127.0.0.1', '::1') or
            parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path not in ('', '/')):
        raise ValueError('expected an explicit uncredentialed loopback HTTP API')
    if conversation_id in ('.', '..') or not re.fullmatch(r'[A-Za-z0-9_.:-]{1,128}', conversation_id):
        raise ValueError('invalid conversation identity')
    if not math.isfinite(timeout) or not 0 < timeout <= 10:
        raise ValueError('timeout must be positive and at most ten seconds')
    port = parsed.port if parsed.port is not None else 80
    if port == 0:
        raise ValueError('invalid API port')
    deadline = time.monotonic() + timeout
    connection = http.client.HTTPConnection(parsed.hostname, port, timeout=timeout)
    timer = None
    try:
        connection.connect()  # literal loopback: no DNS/proxy or external transport
        owned_socket = connection.sock

        def abort():
            try:
                owned_socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

        timer = threading.Timer(max(0, deadline - time.monotonic()), abort)
        timer.daemon = True
        timer.start()
        connection.request('GET', '/conversations/' + quote(conversation_id, safe='') + '/tracker', headers={'Connection': 'close'})
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError('tracker HTTP status is not 200')  # no redirect/auth retry
        body = response.read(MAX_BYTES + 1)
        if time.monotonic() >= deadline:
            raise TimeoutError('tracker deadline')
        if len(body) > MAX_BYTES:
            raise ValueError('tracker response too large')
        return project(json.loads(body))
    finally:
        if timer:
            timer.cancel()
        connection.close()


def collect(base_url, conversation_id, output, timeout=3):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Refuse existing artifacts BEFORE any request, including previously failed runs.
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        try:
            result = fetch(base_url, conversation_id, timeout)
        except Exception as error:
            result = {'schema': 'rasa.voice-latency-server-projection/v1', 'status': 'not_collected',
                      'error_type': type(error).__name__, 'turns': []}
        json.dump(result, stream, allow_nan=False, indent=2)
        stream.write('\n')
    return 0 if result['status'] == 'collected' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', required=True)
    parser.add_argument('--conversation-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=3)
    args = parser.parse_args()
    try:
        return collect(args.base_url, args.conversation_id, args.output, args.timeout)
    except OSError as error:
        print(json.dumps({'status': 'not_collected', 'error_type': type(error).__name__}))
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
