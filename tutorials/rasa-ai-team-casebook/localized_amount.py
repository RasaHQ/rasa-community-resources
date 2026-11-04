"""Keep fictional two-decimal currency values separate from display language."""
from dataclasses import dataclass
from decimal import Decimal
import json


@dataclass(frozen=True)
class Amount:
    minor: int
    currency: str

    def __post_init__(self):
        if type(self.minor) is not int or self.minor < 0:
            raise ValueError('Nonnegative integer minor units required')
        if self.currency not in {'USD', 'EUR', 'GBP'}:
            raise ValueError('This fixture supports only three two-decimal currencies')

    def display(self, locale):
        if locale not in {'en-US', 'de-DE'}:
            raise ValueError('Unsupported display locale')
        whole, cents = divmod(self.minor, 100)
        groups = f'{whole:,}'
        if locale == 'de-DE':
            groups = groups.replace(',', '.')
        return groups + (',' if locale == 'de-DE' else '.') + f'{cents:02}'


def parse_english_display(text):
    """Plausible wrong boundary: locale-agnostic parsing of already formatted text."""
    return Decimal(text.replace(',', ''))


def demo():
    amount = Amount(100050, 'EUR')
    return {'minor_units': amount.minor, 'currency': amount.currency,
            'english_display': amount.display('en-US'),
            'german_display': amount.display('de-DE'),
            'reparsed_german_as_english': str(parse_english_display(amount.display('de-DE'))),
            'retained_value': str(Decimal(amount.minor) / 100)}


if __name__ == '__main__': print(json.dumps(demo(), indent=2, sort_keys=True))
