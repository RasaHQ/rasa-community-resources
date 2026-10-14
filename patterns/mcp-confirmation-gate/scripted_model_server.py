"""Loopback-only OpenAI-shaped fixture for CLI integration checks.

This is a deterministic script, not a model or a measure of model quality.
It never forwards requests, reads credentials or reports billable token usage.
"""
import argparse
import asyncio
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

from fixture_decisions import Decisions


def serve(port):
    decisions = Decisions()
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def respond(self, status, payload):
            body = json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == '/fixture-inspection':
                self.respond(200, {'requests': requests,
                    'failures': decisions.failures,
                    'saw_description': decisions.saw_description,
                    'saw_result': decisions.saw_result,
                    'resolved': decisions.resolved})
            else:
                self.respond(404, {'error': 'Unknown fixture path'})

        def do_POST(self):
            if self.path != '/v1/chat/completions':
                self.respond(404, {'error': 'Only the scripted completion route exists'})
                return
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 2_000_000:
                self.respond(413, {'error': 'Fixture request size refused'})
                return
            try:
                request = json.loads(self.rfile.read(length))
                if request.get('stream'):
                    raise ValueError('Streaming is outside this fixture')
                messages = request['messages']
                if any(item.get('role') == 'user' and
                        'Yes, record it.' in str(item.get('content'))
                        for item in messages):
                    decisions.phase = 'confirm'
                answer = asyncio.run(decisions.complete(None, messages,
                    request.get('tools')))
                calls = [{'id': call.id, 'type': 'function',
                    'function': {'name': call.tool_name,
                        'arguments': json.dumps(call.tool_args)}}
                    for call in answer.tool_calls or []]
                requests.append({'index': len(requests) + 1,
                    'tool_calls': [call['function']['name'] for call in calls],
                    'scripted': True})
                message = {'role': 'assistant',
                    'content': answer.choices[0] if answer.choices else None}
                if calls:
                    message['tool_calls'] = calls
                self.respond(200, {'id': answer.id, 'object': 'chat.completion',
                    'created': 0, 'model': request['model'],
                    'choices': [{'index': 0, 'message': message,
                        'finish_reason': 'tool_calls' if calls else 'stop'}]})
            except Exception as error:
                decisions.failures.append(type(error).__name__)
                self.respond(400, {'error': {'message': 'Scripted fixture refused the request'}})

    with HTTPServer(('127.0.0.1', port), Handler) as server:
        server.serve_forever()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, required=True)
    args = parser.parse_args()
    if not 1024 <= args.port <= 65535:
        parser.error('Choose an unprivileged loopback port')
    serve(args.port)
