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
        if scope['type'] != 'http' or scope.get('path') not in ('/', '/cards'):
            return await self._app(scope, receive, send)
        headers = scope.get('headers', [])
        hosts = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'host']
        origins = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'origin']
        host = hosts[0] if len(hosts) == 1 else ''
        valid_host = host == '127.0.0.1' or (host.startswith('127.0.0.1:') and host[10:].isdigit())
        local_client = (scope.get('client') or ('', 0))[0] == '127.0.0.1'
        same_origin = not origins or origins == ['http://' + host]
        dashboard = scope.get('path') == '/'
        status = 200
        body = b''
        if not valid_host or not local_client or not same_origin:
            status = 403
        elif scope.get('method') != 'GET' or scope.get('query_string'):
            status = 400
        else:
            try:
                body = DASHBOARD if dashboard else self._render_current().encode('utf-8')
            except Exception:
                # Never echo a rendering exception, source record or capability.
                status = 503
                body = b'Briefing board unavailable'
        response_headers = [
            (b'content-type', b'text/html; charset=utf-8'),
            (b'cache-control', b'no-store'),
            (b'referrer-policy', b'no-referrer'),
            (b'x-content-type-options', b'nosniff'),
            (b'content-security-policy',
             b"default-src 'none'; style-src 'unsafe-inline'; frame-src 'self' http://127.0.0.1:5005; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
             if dashboard else b"default-src 'none'; style-src 'unsafe-inline'; frame-ancestors 'self'; base-uri 'none'; form-action 'none'"),
        ]
        if status == 200 and not dashboard:
            response_headers.append((b'refresh', b'2'))
        await send({'type': 'http.response.start', 'status': status, 'headers': response_headers})
        await send({'type': 'http.response.body', 'body': body})


# Page composition only: Core still renders every card and validates its values.
# The card frame refreshes independently so conversation input is never reloaded.
DASHBOARD = b"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Flight briefing</title>
<style>body{margin:0;background:#f4f5f7;color:#17212b;font:16px system-ui,sans-serif}
header{padding:12px 20px}h1{font-size:20px;margin:0}main{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 12px 12px;height:calc(100vh - 70px)}
iframe{border:1px solid #d3d7df;border-radius:8px;background:white;width:100%;height:100%}
@media(max-width:800px){main{grid-template-columns:1fr;height:auto}iframe{height:75vh}}
</style></head><body><header><h1>Flight briefing</h1></header><main>
<iframe title="Mantle conversation" src="http://127.0.0.1:5005/webhooks/inspector/inspect.html?projectUrl=http%3A%2F%2F127.0.0.1%3A5005"></iframe>
<iframe title="Validated source cards" src="/cards"></iframe>
</main></body></html>"""
