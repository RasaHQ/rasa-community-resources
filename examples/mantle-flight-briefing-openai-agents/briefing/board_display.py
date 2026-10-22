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
<style>body{margin:0;background:#f4f5f7;color:#17212b;font:16px system-ui,sans-serif;display:grid;grid-template-rows:auto minmax(0,1fr);height:100vh}
header{padding:12px 20px}h1{font-size:20px;margin:0}main{display:grid;grid-template-columns:1fr 1fr;gap:12px;padding:0 12px 12px;min-height:0}
iframe{border:1px solid #d3d7df;border-radius:8px;background:white;width:100%;height:100%}
@media(max-width:800px){body{height:auto}main{grid-template-columns:1fr;height:auto}iframe{height:75vh}}
</style></head><body><header><h1>Flight briefing</h1></header><main>
<iframe title="Mantle conversation" src="http://127.0.0.1:5005/webhooks/inspector/inspect.html?projectUrl=http%3A%2F%2F127.0.0.1%3A5005"></iframe>
<iframe title="Validated source cards" src="/cards"></iframe>
</main></body></html>"""


def dashboard_html(host):
    validate_host(host)
    return DASHBOARD.replace(b'127.0.0.1', host.encode()).replace(
        b'http%3A%2F%2F127.0.0.1%3A5005', quote('http://' + host + ':5005', safe='').encode())


# Semantic Rasa roles from supplied brand tokens v0.2.0 (2026-10-16).
# No font binaries or remote font loads: the declared stacks fall back locally.
BRAND_CSS = """
:root{--rasa-bg:#FAF6F0;--rasa-panel:#FFFBF5;--rasa-ink:#181210;--rasa-muted:#524A43;--rasa-border:#C8C0B6;--rasa-link:#AA1E54}
body{background:var(--rasa-bg);color:var(--rasa-ink);font-family:"STK Bureau Sans",Inter,Arial,sans-serif;line-height:1.5}
h1,h2,h3{font-family:"STK Bureau Serif",Newsreader,Georgia,serif;font-weight:400}
a{color:var(--rasa-link)}a:focus-visible,iframe:focus-visible{outline:3px solid var(--rasa-link);outline-offset:3px}
header{border-bottom:1px solid var(--rasa-border);margin-bottom:16px;background:var(--rasa-panel)}
iframe{border-color:var(--rasa-border);border-radius:16px;background:var(--rasa-panel);box-sizing:border-box}
blockquote{border-left:4px solid #E85A91;background:var(--rasa-panel);padding:16px;margin:20px 0;font-size:18px}
.eyebrow{font-family:"STK Bureau Sans Mono","JetBrains Mono",ui-monospace,monospace;font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--rasa-muted)}
.search-choice{background:var(--rasa-panel);border:1px solid var(--rasa-border);border-radius:16px;padding:16px;margin:12px 0;overflow-wrap:anywhere}
.source-note{font-size:14px;color:var(--rasa-muted)}
"""


def brand_document(document):
    return document.replace('</head>', '<style>' + BRAND_CSS + '</style></head>', 1)


DASHBOARD = brand_document(DASHBOARD.decode().replace('<h1>Flight briefing</h1>',
    '<p class="eyebrow">Rasa - Flight briefing</p><h1>Your flight, your meeting</h1>')).encode()


def position_age_text(seconds):
    import math
    if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or not 0 <= seconds <= 120:
        raise ValueError('invalid_position_age')
    if seconds < 10:
        return 'just now'
    if seconds < 60:
        return f'{int(seconds)} s old'
    return f'{int(seconds // 60)} min old'


def start_panel(status, *, discovery=None):
    from html import escape
    choices = ''
    if discovery and discovery.get('candidates'):
        from briefing.traveller import discovery_notice, flight_name, reference
        discovery_notice(discovery)  # Refuse unchecked or unbounded choice values.
        rows = []
        for row in discovery['candidates']:
            city = reference()['origin_cities'].get(row['origin'], {}).get('city', row['origin'])
            rows.append('<li class="search-choice"><strong>' + escape(flight_name(row['callsign']))
                + '</strong> from ' + escape(city) + '<br>Estimated landing in about '
                + escape(str(row['landing_estimate_minutes'])) + ' minutes. Position '
                + escape(position_age_text(row['position_age_seconds'])) + '.</li>')
        choices = '<h2>Which flight would you like?</h2><ol>' + ''.join(rows) + '</ol><p class="source-note">'
        choices += escape(discovery['label']) + '. Route table date: ' + escape(discovery['source_date'])
        choices += '. ' + escape(discovery['coverage']) + ' Landing estimates are computed from position and speed, not airline times. '
        choices += '<a href="https://github.com/vradarserver/standing-data/tree/03cd2417bb217476aa1f560dcb1a136205deff5d">Virtual Radar Server standing-data</a> (CC0-1.0).</p>'
        if discovery.get('partial'):
            choices += '<p class="source-note">This search is partial; more flights may be present.</p>'
    document = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Start your briefing</title>
<style>body{margin:24px}li{margin:12px 0}h1{font-size:28px}p{max-width:65ch}</style></head><body>
<p class="eyebrow">Rasa - Your arrival plan</p><h1>Start your briefing</h1><p><strong>""" + escape(status) + """</strong></p>
<p>Tell the assistant where you are heading. If you do not know your flight, it can help you choose one already in the air.</p>
<blockquote>I'm heading to New York. Which flights are already in the air?</blockquote>
""" + choices + """
<p>When you have chosen a flight, tell it when your meeting is - for example, tomorrow at 6 pm. It uses the destination's local time.</p>
<ul><li><strong>Your flight</strong>: observed position and a calculated landing estimate.</li>
<li><strong>Arrival weather</strong>: the forecast at your destination.</li>
<li><strong>Time for your meeting</strong>: your arrival, a labelled airport-to-city allowance and your meeting. You can change the allowance.</li>
<li><strong>Currency watchlist</strong>: daily ECB reference rates, not live quotes.</li></ul>
<p>The details appear here. Keep chatting in your own words beside this panel.</p>
</body></html>"""
    return brand_document(document)
