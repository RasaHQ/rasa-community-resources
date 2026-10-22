"""Completion refuses an empty page, three cards and unavailable/duplicate cards."""
import unittest
from check_demo import EXPECTED, inspect_cards


def board(names=EXPECTED, unavailable=None):
    return ''.join('<article class="zc-card zc-' + name + '"><h3>' + name + '</h3>'
                   + ('<p class="zc-unavail">unavailable</p>' if name == unavailable else '<p>source result</p>')
                   + '</article>' for name in names)


class CompletionControls(unittest.TestCase):
    def test_all_four_available_are_required(self):
        self.assertTrue(inspect_cards(board()))
        self.assertFalse(inspect_cards('Four cards: flight, weather, timeline, market'))
        self.assertFalse(inspect_cards(board(EXPECTED[:3])))
        self.assertFalse(inspect_cards(board(EXPECTED[:3] + (EXPECTED[0],))))

    def test_empty_answers_cannot_pass_with_titles_and_provenance(self):
        empty = board().replace('<p>source result</p>', '<p> \n </p><p class="zc-prov">fetched 07:00 UTC</p>')
        self.assertFalse(inspect_cards(empty))
        for name in EXPECTED:
            with self.subTest(card=name):
                html = board().replace('<h3>' + name + '</h3><p>source result</p>',
                                       '<h3>' + name + '</h3><p> </p>')
                self.assertFalse(inspect_cards(html))

    def test_recorded_and_public_checks_cannot_accept_each_others_mode(self):
        replay = board().replace('<h3>', '<span>REPLAY</span><h3>')
        self.assertFalse(inspect_cards(replay))
        self.assertTrue(inspect_cards(replay, require_replay=True))
        self.assertFalse(inspect_cards(board(), require_replay=True))
        mixed = board().replace('<h3>', '<span>REPLAY</span><h3>', 1)
        self.assertFalse(inspect_cards(mixed))
        self.assertFalse(inspect_cards(mixed, require_replay=True))

    def test_each_unavailable_card_refuses_completion(self):
        for name in EXPECTED:
            with self.subTest(card=name):
                self.assertFalse(inspect_cards(board(unavailable=name)))


if __name__ == '__main__':
    unittest.main()
