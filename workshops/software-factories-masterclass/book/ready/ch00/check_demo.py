"""Read the local product page; four empty or unavailable cards are not completion.
sow: software-factories-masterclass-SOW-02
"""
from html.parser import HTMLParser
import argparse
import re
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
                            'unavailable': 'zc-unavailable' in classes, 'replay': False, 'text': []}
        if self.current is not None and 'zc-unavail' in classes:
            self.current['unavailable'] = True

    def handle_data(self, text):
        if self.current is not None:
            self.current['text'].append(text)
            if text.strip() == 'REPLAY':
                self.current['replay'] = True

    def handle_endtag(self, tag):
        if tag == 'article' and self.current is not None:
            self.cards.append(self.current)
            self.current = None


def inspect_cards(html, *, require_replay=False, transfer_minutes=None):
    parser = Cards()
    parser.feed(html)
    components = [card['component'] for card in parser.cards]
    if (None in components or len(components) != 4 or sorted(components) != sorted(EXPECTED)
            or any(card['unavailable'] for card in parser.cards)):
        return False
    if require_replay and not all(card['replay'] for card in parser.cards):
        return False
    if not require_replay and any(card['replay'] for card in parser.cards):
        return False
    if transfer_minutes is not None:
        timeline = next(card for card in parser.cards if card['component'] == 'arrival_timeline')
        if not re.search(r'\bTransfer:\s*' + str(transfer_minutes) + r'\s*min\b', ' '.join(timeline['text'])):
            return False
    return True


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, newurl):
        return None


def main():
    class SafeParser(argparse.ArgumentParser):
        def error(self, message):
            raise ValueError('invalid_completion_options')
    parser = SafeParser()
    parser.add_argument('--recorded', action='store_true')
    parser.add_argument('--transfer-minutes', type=int, choices=(30, 120))
    try:
        args = parser.parse_args()
    except ValueError:
        print('Use --recorded and, optionally, --transfer-minutes 30 or 120.')
        return 2
    # Fixed local address only; no credential, briefing ID, URL or response body is logged.
    request = urllib.request.Request('http://127.0.0.1:8942/cards')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    try:
        with opener.open(request, timeout=5) as response:
            body = response.read(1048577)
            if response.status != 200 or len(body) > 1048576:
                raise ValueError()
        ready = inspect_cards(body.decode('utf-8'), require_replay=args.recorded, transfer_minutes=args.transfer_minutes)
    except (OSError, UnicodeError, ValueError, urllib.error.URLError):
        print('Could not check the local card page. Start this checkpoint and try again.')
        return 2
    if not ready:
        print('NOT DONE: need four available cards with the requested replay mode and transfer allowance. Read the page and revise through the agent.')
        return 1
    print('ch00 OK: four available cards' + (' in REPLAY mode' if args.recorded else '')
          + (', requested transfer ' + str(args.transfer_minutes) + ' min' if args.transfer_minutes is not None else '') + '.')
    print('This checks the displayed result, not voice, model reasoning, a different session, or future source availability.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
