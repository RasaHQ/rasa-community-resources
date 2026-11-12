"""Actual pinned SDK parsing at the custom engine boundary; no network calls."""
import json
import unittest

from rasa.core.channels.voice_stream.asr.asr_event import NewTranscript
from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramV2ASRConfig
from rasa.core.channels.voice_stream.asr.deepgram.engine import _DeepgramV2
from voice_privacy import OptOutASR


class FinalTranscriptTests(unittest.TestCase):
    def engine(self):
        engine=OptOutASR.__new__(OptOutASR)
        engine._handler=_DeepgramV2(DeepgramV2ASRConfig())
        return engine

    def frame(self,event,text='',turn=0):
        return {'type':'TurnInfo','request_id':'fictional-request','turn_index':turn,
                'event':event,'transcript':text}

    def test_final_only_short_reply_reaches_sdk_once(self):
        for encode in (lambda value:value,json.dumps,lambda value:json.dumps(value).encode()):
            with self.subTest(encode=encode):
                engine=self.engine()
                self.assertIsNone(engine.engine_event_to_asr_event(encode(self.frame('StartOfTurn','Yes.'))))
                with self.assertLogs('voice_privacy',level='INFO') as logs:
                    final=engine.engine_event_to_asr_event(encode(self.frame('EndOfTurn','Yes.')))
                self.assertNotIn('Yes.',str(logs.output))
                self.assertNotIn('fictional-request',str(logs.output))
                self.assertIsInstance(final,NewTranscript)
                self.assertEqual(final.text,'Yes.')
                self.assertIsNone(engine.engine_event_to_asr_event(encode(self.frame('EndOfTurn','Yes.'))))

    def test_final_text_supersedes_interim_without_rewriting_it(self):
        engine=self.engine()
        engine.engine_event_to_asr_event(self.frame('StartOfTurn'))
        engine.engine_event_to_asr_event(self.frame('Update','Yeah.'))
        final=engine.engine_event_to_asr_event(self.frame('EndOfTurn','Yes.'))
        self.assertEqual(final.text,'Yes.')
        self.assertIsNone(engine.engine_event_to_asr_event(self.frame('EndOfTurn','Yes.')))

    def test_empty_turn_never_creates_confirmation_and_later_turn_still_arrives(self):
        engine=self.engine()
        engine.engine_event_to_asr_event(self.frame('StartOfTurn'))
        engine.engine_event_to_asr_event(self.frame('Update','Yes.'))
        self.assertIsNone(engine.engine_event_to_asr_event(self.frame('EndOfTurn')))
        engine.engine_event_to_asr_event(self.frame('StartOfTurn',turn=1))
        final=engine.engine_event_to_asr_event(self.frame('EndOfTurn','No.',turn=1))
        self.assertEqual(final.text,'No.')
        self.assertIsNone(engine.engine_event_to_asr_event(self.frame('EndOfTurn','Yes.',turn=0)))
