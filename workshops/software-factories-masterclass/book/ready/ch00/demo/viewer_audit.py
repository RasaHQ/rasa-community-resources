"""Optional preview access metadata only: no path, query, body, headers or keys."""
from datetime import datetime, timezone
import ipaddress
import json
import os


def record_access(component, peer):
    target = os.environ.get('BRIEFING_VIEWER_AUDIT')
    if not target:
        return
    try:
        peer = str(ipaddress.ip_address(peer))
    except ValueError:
        peer = 'unknown'
    record = {'at': datetime.now(timezone.utc).isoformat(),
              'component': component, 'peer': peer}
    with open(target, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps(record, separators=(',', ':')) + '\n')


def install_inspector_audit():
    from rasa.core import run
    original = run.configure_app
    def configure(*args, **kwargs):
        app = original(*args, **kwargs)
        async def access(request):
            record_access('inspector', request.ip)
        app.register_middleware(access, 'request')
        return app
    run.configure_app = configure
