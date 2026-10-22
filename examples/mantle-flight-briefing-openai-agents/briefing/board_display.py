"""Local display transport; all card rendering belongs to zeocore.

No job identifier or credential is accepted by this endpoint. The service
selects its current classroom board internally. This wrapper starts no server.
"""
from collections.abc import Callable


class BoardDisplay:
    def __init__(self, app, *, render_current: Callable[[], str]):
        self._app = app
        self._render_current = render_current

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') != '/cards':
            return await self._app(scope, receive, send)
        headers = scope.get('headers', [])
        hosts = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'host']
        origins = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'origin']
        host = hosts[0] if len(hosts) == 1 else ''
        valid_host = host == '127.0.0.1' or (host.startswith('127.0.0.1:') and host[10:].isdigit())
        local_client = (scope.get('client') or ('', 0))[0] == '127.0.0.1'
        same_origin = not origins or origins == ['http://' + host]
        status = 200
        body = b''
        if not valid_host or not local_client or not same_origin:
            status = 403
        elif scope.get('method') != 'GET' or scope.get('query_string'):
            status = 400
        else:
            try:
                body = self._render_current().encode('utf-8')
            except Exception:
                # Never echo a rendering exception, source record or capability.
                status = 503
                body = b'REPLAY board unavailable'
        response_headers = [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'cache-control', b'no-store'),
            (b'referrer-policy', b'no-referrer'),
            (b'x-content-type-options', b'nosniff'),
            (b'content-security-policy', b"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"),
        ]
        if status == 200:
            response_headers.append((b'refresh', b'2'))
        await send({'type': 'http.response.start', 'status': status, 'headers': response_headers})
        await send({'type': 'http.response.body', 'body': body})
