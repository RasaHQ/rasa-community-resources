"""Backend voice qualification is explicit when either dependency pin changes.
The private engine repair itself remains byte-equal to the qualified v1.
"""
from importlib.metadata import PackageNotFoundError, version

QUALIFIED_PINS = frozenset({('3.21.0.dev5', '0.35.6'), ('3.21.0.dev5', '0.36.3')})


def require_qualified_voice_pins(version_lookup=None):
    lookup = version if version_lookup is None else version_lookup
    try:
        pins = (lookup('rasa-pro'), lookup('zeocore'))
    except PackageNotFoundError:
        raise RuntimeError('Voice dependencies are missing; run setup before enabling voice.') from None
    if pins not in QUALIFIED_PINS:
        raise RuntimeError('Voice repair needs requalification for these dependency pins. Run the documented offline and three-turn checks before extending QUALIFIED_PINS.')
    return pins
