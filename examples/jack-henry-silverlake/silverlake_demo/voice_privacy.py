"""Supported custom speech engines: opt out on each constructed request.

This controls the model-improvement flag, not the provider's entire retention
policy. Use only fictional speech and verify the real browser path separately.
"""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rasa.core.channels.voice_stream.asr.deepgram.engine import DeepgramASR
from rasa.core.channels.voice_stream.tts.deepgram import DeepgramTTS


def _approved(url):
    parts = urlsplit(url)
    if (parts.scheme != 'wss' or parts.netloc != 'api.deepgram.com'
            or parts.path not in {'/v1/listen', '/v2/listen', '/v1/speak'}
            or parts.fragment):
        raise ValueError('unapproved_speech_endpoint')
    return parts


class OptOutASR(DeepgramASR):
    def _get_api_url(self):
        url = super()._get_api_url()
        _approved(url)
        return url

    def _get_query_params(self):
        values = dict(parse_qsl(super()._get_query_params()))
        values['mip_opt_out'] = 'true'
        return urlencode(values)


class OptOutTTS(DeepgramTTS):
    def get_websocket_url(self, config):
        parts = _approved(super().get_websocket_url(config))
        values = dict(parse_qsl(parts.query))
        values['mip_opt_out'] = 'true'
        return urlunsplit(parts._replace(query=urlencode(values)))
