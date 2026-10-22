"""One authenticated MCP tool and a labelled Inspector entry page."""
import asyncio
from datetime import timedelta
import json
import os
import secrets
from datetime import datetime, timezone
from html import escape

from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
import uvicorn


def audit(peer, component):
    path = os.environ.get('FACTORY_VIEWER_AUDIT')
    if path:
        with open(path, 'a') as f:
            f.write(json.dumps({'at': datetime.now(timezone.utc).isoformat(), 'peer': peer, 'component': component}) + '\n')


class Authenticated:
    def __init__(self, app, token):
        self.app, self.token = app, token.encode()

    async def __call__(self, scope, receive, send):
        if scope['type'] == 'http':
            headers = dict(scope.get('headers', []))
            supplied = headers.get(b'authorization', b'')
            if not secrets.compare_digest(supplied, b'Bearer ' + self.token):
                return await JSONResponse({'error': 'unauthenticated'}, status_code=401)(scope, receive, send)
        return await self.app(scope, receive, send)


def mcp_app():
    server = FastMCP('factory', host='127.0.0.1', port=int(os.environ.get('FACTORY_MCP_PORT', '8948')), stateless_http=True, json_response=True)

    busy = asyncio.Lock()

    @server.tool()
    async def run_factory(request: str) -> dict:
        """Judge a supplied attempt using the existing protected gate. No code generation or release."""
        import asyncio
        from factory_gate import run_factory as execute
        normalized = ' '.join(request.lower().strip().rstrip('.!?').split())
        kinds = {'show at most three currencies on the market card': 'good',
                 'show at most 3 currencies on the market card': 'good',
                 'use the attempt that ignores the limit': 'ignores-limit'}
        kind = kinds.get(normalized)
        if kind is None:
            return {'verdict': 'NOT_READY', 'failing_test': None, 'fingerprint': None,
                    'seconds': 0, 'reason': 'Use one of the two displayed requests; no arbitrary code or paths are accepted.'}
        if busy.locked():
            return {'verdict': 'NOT_READY', 'failing_test': None, 'fingerprint': None,
                    'seconds': 0, 'reason': 'A factory check is still running. Wait for its result.'}
        expiry = datetime.fromisoformat(os.environ['FACTORY_EXPIRES_AT'].replace('Z', '+00:00'))
        if datetime.now(timezone.utc) + timedelta(seconds=350) >= expiry:
            return {'verdict': 'NOT_READY', 'failing_test': None, 'fingerprint': None,
                    'seconds': 0, 'reason': 'Not enough time remains before the preview expiry.'}
        async with busy:
            mode = os.environ.get('FACTORY_BUILDER_MODE', 'SCRIPTED')
            result = await asyncio.to_thread(execute, kind, mode=mode,
                worker_python=os.environ['FACTORY_WORKER_PYTHON'],
                evidence_root=os.environ['FACTORY_EVIDENCE_ROOT'],
                env_file=os.environ.get('FACTORY_ENV_FILE') or None)
            # Local evidence and attempt paths never enter the conversation.
            allowed = ('verdict', 'failing_test', 'fingerprint', 'seconds',
                       'mode', 'builder_calls', 'reason')
            return {key: result[key] for key in allowed if key in result}

    token = os.environ['FACTORY_MCP_TOKEN']
    if len(token) < 32:
        raise ValueError('runtime transport token required')
    return Authenticated(server.streamable_http_app(), token)


def frontend(host):
    async def index(request):
        peer = request.client.host
        audit(peer, 'entry')
        if peer not in os.environ['FACTORY_ALLOWED_PEERS'].split(','):
            return HTMLResponse('Tailnet only', status_code=403)
        name = os.environ.get('FACTORY_VIEWER_NAME', host)
        inspector_port = int(os.environ.get('FACTORY_INSPECTOR_PORT', '5007'))
        url = f'http://{name}:{inspector_port}/webhooks/inspector/inspect.html?projectUrl=http%3A%2F%2F{name}%3A{inspector_port}'
        mode = os.environ.get('FACTORY_BUILDER_MODE', 'SCRIPTED')
        label = ('Mantle selection SCRIPTED · LIVE OpenAI Agents API builder: gpt-6-astra · expected 15 to 150 US cents per run (estimate, not a cap) · up to 5 minutes · real protected gate · nothing released' if mode == 'LIVE' else 'SCRIPTED tool selection · supplied attempts · real protected gate · no model calls · nothing released')
        return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>Mantle factory agent</title><style>body{margin:0;font:18px system-ui}header{padding:16px;background:#342b67;color:white}iframe{border:0;width:100%;height:85vh}</style><header>' + escape(label) + '</header><iframe allow="microphone; autoplay" title="Mantle factory conversation" src="' + escape(url, quote=True) + '"></iframe></html>')
    return Starlette(routes=[Route('/', index)])


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'mcp':
        uvicorn.run(mcp_app(), host='127.0.0.1', port=int(os.environ.get('FACTORY_MCP_PORT', '8948')), log_level='warning', access_log=False)
    else:
        host = os.environ['FACTORY_HOST']
        uvicorn.run(frontend(host), host=host, port=int(os.environ.get('FACTORY_ENTRY_PORT', '8947')), log_level='warning', access_log=False)
