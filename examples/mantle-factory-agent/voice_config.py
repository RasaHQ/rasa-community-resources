"""Optional maintained-engine voice configuration; never probes a provider.

The launcher may merge these channels into its private runtime project only
when the environment key is present. Omit them on missing keys or voice startup
failure so the normal inspector text path remains available.
"""
import os

VOICE_OFF_TEXT = 'Voice is off; set DEEPGRAM_API_KEY in your environment to enable it, or continue with text.'
VOICE_FAILED_TEXT = 'Voice could not connect; continuing with text.'


def voice_channels(environment=None):
    environment = os.environ if environment is None else environment
    if not environment.get('DEEPGRAM_API_KEY', '').strip():
        return {}
    # The engine reads its required DEEPGRAM_API_KEY directly from the process
    # environment. Never copy the value into this configuration or a URL.
    asr = {'name': 'deepgram', 'language_map': {'en': {'model': 'flux-general-en'}}}
    tts = {'name': 'deepgram', 'language_map': {'en': {'model': 'aura-2-andromeda-en'}}}
    return {'inspector': {'enabled': True, 'asr': asr, 'tts': tts}}
