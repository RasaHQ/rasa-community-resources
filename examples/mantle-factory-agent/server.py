"""One authenticated MCP tool and a labelled Inspector entry page."""
import ipaddress
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
    server = FastMCP('factory', host='127.0.0.1', port=8948, stateless_http=True, json_response=True)

    @server.tool()
    async def run_factory(request: str) -> dict:
        """Judge a supplied attempt using the existing protected gate. No code generation or release."""
        import asyncio
        from factory_gate import run_factory as execute
        normalized = ' '.join(request.lower().strip().rstrip('.!?').split())
        kinds = {'show at most three currencies on the market card': 'good',
                 'use the attempt that ignores the limit': 'ignores-limit'}
        kind = kinds.get(normalized)
        if kind is None:
            return {'verdict': 'NOT_READY', 'failing_test': None, 'fingerprint': None,
                    'seconds': 0, 'reason': 'Use one of the two displayed requests; no arbitrary code or paths are accepted.'}
        return await asyncio.to_thread(execute, kind)

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
        url = f'http://{name}:5007/webhooks/inspector/inspect.html?projectUrl=http%3A%2F%2F{name}%3A5007'
        return HTMLResponse('<!doctype html><html lang="en"><meta charset="utf-8"><title>Mantle factory agent</title><style>body{margin:0;font:18px system-ui}header{padding:16px;background:#342b67;color:white}iframe{border:0;width:100%;height:85vh}</style><header>SCRIPTED tool selection · real protected acceptance gate · supplied attempts · no model calls · nothing released</header><iframe title="Mantle factory conversation" src="' + escape(url, quote=True) + '"></iframe></html>')
    return Starlette(routes=[Route('/', index)])


if __name__ == '__main__':
    import sys
    if sys.argv[1] == 'mcp':
        uvicorn.run(mcp_app(), host='127.0.0.1', port=8948, log_level='warning', access_log=False)
    else:
        host = os.environ['FACTORY_HOST']
        uvicorn.run(frontend(host), host=host, port=8947, log_level='warning', access_log=False)
