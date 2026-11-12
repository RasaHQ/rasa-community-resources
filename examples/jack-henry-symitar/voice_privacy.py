"""Supported custom speech engines: opt out on each constructed request.

This controls the model-improvement flag, not the provider's entire retention
policy. Use only fictional speech and verify the real browser path separately.
"""
import json
import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript
from rasa.core.channels.voice_stream.asr.deepgram.engine import DeepgramASR
from rasa.core.channels.voice_stream.tts.deepgram import DeepgramTTS


def _approved(url):
    parts = urlsplit(url)
    if (parts.scheme != 'wss' or parts.netloc != 'api.deepgram.com'
            or parts.path not in {'/v1/listen', '/v2/listen', '/v1/speak'}
            or parts.fragment):
        raise ValueError('unapproved_speech_endpoint')
    return parts


_log=logging.getLogger(__name__)


class OptOutASR(DeepgramASR):
    def engine_event_to_asr_event(self, event):
        # Flux EndOfTurn owns the final transcript. SDK 3.21 otherwise drops a
        # short reply with no Update, or commits an older interim hypothesis.
        # This is the custom ASREngine interface; installed SDK bytes stay intact.
        data=json.loads(event) if isinstance(event,(str,bytes)) else event
        if (self._handler.api_version!='v2' or not isinstance(data,dict)
                or data.get('type')!='TurnInfo' or data.get('event')!='EndOfTurn'):
            return super().engine_event_to_asr_event(event)
        request=data.get('request_id');turn=data.get('turn_index')
        if not isinstance(request,str) or not request or type(turn) is not int or turn<0:
            return super().engine_event_to_asr_event(event)
        completed=getattr(self,'_completed_flux_turns',{})
        if turn<=completed.get(request,-1):
            _log.info('symitar.asr.final duplicate=true')
            return None
        # Let the SDK clear its interim buffer even for an empty final turn.
        base=super().engine_event_to_asr_event(event)
        completed[request]=turn;self._completed_flux_turns=completed
        text=data.get('transcript')
        present=isinstance(text,str) and bool(text.strip())
        _log.info('symitar.asr.final %s',json.dumps({'has_text':present,
            'base_emitted_final':isinstance(base,NewTranscript),'duplicate':False}))
        return NewTranscript(text=text) if present else None

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
