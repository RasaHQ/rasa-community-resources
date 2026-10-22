"""Read the local product page; four empty or unavailable cards are not completion.
sow: software-factories-masterclass-SOW-02
"""
from html.parser import HTMLParser
import urllib.error
import urllib.request

EXPECTED = ('flight_status', 'weather_hourly', 'arrival_timeline', 'market_watchlist')


class Cards(HTMLParser):
    def __init__(self):
        super().__init__()
        self.current = None
        self.cards = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        classes = attrs.get('class', '').split()
        if tag == 'article' and 'zc-card' in classes:
            self.current = {'component': next((name for name in EXPECTED if 'zc-' + name in classes), None),
                            'unavailable': 'zc-unavailable' in classes}
        if self.current is not None and 'zc-unavail' in classes:
            self.current['unavailable'] = True

    def handle_endtag(self, tag):
        if tag == 'article' and self.current is not None:
            self.cards.append(self.current)
            self.current = None


def inspect_cards(html):
    parser = Cards()
    parser.feed(html)
    components = [card['component'] for card in parser.cards]
    return (len(components) == 4 and sorted(components) == sorted(EXPECTED)
            and not any(card['unavailable'] for card in parser.cards)) if None not in components else False


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    # Fixed local address only; no credential, briefing ID, URL or response body is logged.
    request = urllib.request.Request('http://127.0.0.1:8942/cards')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            body = response.read(1048577)
            if response.status != 200 or len(body) > 1048576:
                raise ValueError()
        ready = inspect_cards(body.decode('utf-8'))
    except (OSError, UnicodeError, ValueError, urllib.error.URLError):
        print('Could not check the local card page. Start this checkpoint and try again.')
        return 2
    if not ready:
        print('NOT DONE: complete a briefing with four available cards. Read missing-input or source reasons in the page.')
        return 1
    print('ch00 OK: local HTTP page contains all four available source cards.')
    print('This checks the displayed result, not voice, model reasoning, a different session, or future source availability.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
