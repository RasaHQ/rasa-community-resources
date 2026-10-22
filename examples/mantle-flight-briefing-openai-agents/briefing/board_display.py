"""Local display transport; all card rendering belongs to zeocore.

No job identifier or credential is accepted by this endpoint. The service
selects its current classroom board internally. This wrapper starts no server.
"""
from collections.abc import Callable
from urllib.parse import quote
from demo_host import validate_host, display_hosts, allowed_client


class BoardDisplay:
    def __init__(self, app, *, render_current: Callable[[], str], host="127.0.0.1"):
        self._host = validate_host(host)
        self._app = app
        self._render_current = render_current

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http' or scope.get('path') not in ('/', '/cards'):
            return await self._app(scope, receive, send)
        from viewer_audit import record_access
        record_access('cards', (scope.get('client') or ('unknown', 0))[0])
        headers = scope.get('headers', [])
        hosts = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'host']
        origins = [v.decode('ascii', errors='replace') for k, v in headers if k.lower() == b'origin']
        host = hosts[0] if len(hosts) == 1 else ''
        valid_host = any(host == candidate or (host.startswith(candidate + ':')
                         and host[len(candidate) + 1:].isdigit()) for candidate in display_hosts(self._host))
        local_client = allowed_client((scope.get('client') or ('', 0))[0], self._host)
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
                body = dashboard_html(self._host) if dashboard else self._render_current().encode('utf-8')
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
             ("default-src 'none'; style-src 'unsafe-inline'; frame-src 'self' http://" + self._host + ":5005; frame-ancestors 'none'; base-uri 'none'; form-action 'none'").encode()
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


def dashboard_html(host):
    validate_host(host)
    return DASHBOARD.replace(b'127.0.0.1', host.encode()).replace(
        b'http%3A%2F%2F127.0.0.1%3A5005', quote('http://' + host + ':5005', safe='').encode())


def start_panel(status):
    from html import escape
    return """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Start your briefing</title>
<style>body{font:16px system-ui,sans-serif;color:#17212b;margin:24px;line-height:1.5}
code{display:block;white-space:normal;overflow-wrap:anywhere;background:#f4f5f7;padding:12px;border-radius:8px}
li{margin:12px 0}h1{font-size:24px}p{max-width:65ch}</style></head><body>
<h1>Start your briefing</h1><p><strong>""" + escape(status) + """</strong></p>
<p>Tell the Mantle assistant your flight callsign, destination, meeting time and assumed transfer duration.</p>
<code>callsign=TEST123 destination=EDDF meeting=2026-10-22T12:00:00Z transfer=45</code>
<p>This is example syntax. Replace TEST123 with a currently airborne callsign and set your own meeting date and time.</p>
<ul><li><strong>Flight status</strong>: observed position from ADSB.lol; an arrival estimate is a calculation, not an airline time.</li>
<li><strong>Arrival weather</strong>: MET Norway forecast for the destination you state.</li>
<li><strong>Arrival timeline</strong>: calculated from the flight estimate, your meeting time and assumed transfer.</li>
<li><strong>Market watchlist</strong>: ECB daily EUR reference rates; these are not live quotes.</li></ul>
<p>Enter the journey in the conversation beside this panel. The cards appear here as the checks finish.</p>
</body></html>"""
