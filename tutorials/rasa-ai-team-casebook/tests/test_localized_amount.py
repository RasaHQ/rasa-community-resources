import sys
import unittest
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from localized_amount import Amount, parse_english_display


class LocalizedAmount(unittest.TestCase):
    def test_language_change_does_not_change_confirmed_value(self):
        amount = Amount(100050, 'EUR')
        self.assertEqual(amount.display('en-US'), '1,000.50')
        self.assertEqual(amount.display('de-DE'), '1.000,50')
        self.assertEqual(amount.minor, 100050)
        self.assertEqual(amount.currency, 'EUR')

    def test_wrong_parser_can_succeed_with_wrong_value(self):
        self.assertEqual(parse_english_display('1.000,50'), Decimal('1.00050'))
        self.assertNotEqual(parse_english_display('1.000,50'), Decimal('1000.50'))

    def test_small_number_can_be_wrong_in_opposite_direction(self):
        self.assertEqual(parse_english_display(Amount(150, 'EUR').display('de-DE')), Decimal('150'))

    def test_minor_unit_and_currency_are_immutable(self):
        amount = Amount(150, 'EUR')
        with self.assertRaises(FrozenInstanceError): amount.minor = 15000
        with self.assertRaises(FrozenInstanceError): amount.currency = 'USD'

    def test_all_fixture_values_roundtrip_in_original_english_domain(self):
        for minor in range(0, 100001):
            self.assertEqual(parse_english_display(Amount(minor, 'USD').display('en-US')), Decimal(minor)/100)

    def test_invalid_minor_units_and_currency_rejected(self):
        for value in [-1, 1.5, True, '100']:
            with self.assertRaises(ValueError): Amount(value, 'EUR')
        with self.assertRaises(ValueError): Amount(100, 'JPY')

    def test_unsupported_locale_is_not_guessed(self):
        with self.assertRaises(ValueError): Amount(100, 'EUR').display('fr-FR')


if __name__ == '__main__': unittest.main()
