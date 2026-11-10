import unittest
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.processors.aggregators.llm_response_universal import (
    LLMUserAggregator,
    LLMAssistantAggregator,
)
from rasa_dialogue.compose import with_rasa
from rasa_dialogue.processor import RasaDialogueProcessor


class ExistingTransport:
    def __init__(self):
        self.source, self.sink = FrameProcessor(), FrameProcessor()

    def input(self):
        return self.source

    def output(self):
        return self.sink


class NativeComposition(unittest.TestCase):
    def test_existing_media_processors_remain_once_in_native_pipeline(self):
        transport, stt, tts = ExistingTransport(), FrameProcessor(), FrameProcessor()

        async def ask(text):
            raise AssertionError("Construction cannot make a dialogue request")

        pipeline = with_rasa(transport, stt, tts, ask)
        processors = pipeline.processors[1:-1]
        self.assertIs(processors[0], transport.source)
        self.assertIs(processors[1], stt)
        self.assertIsInstance(processors[2], LLMUserAggregator)
        self.assertIsNone(processors[2]._params.empty_user_turn)
        self.assertIsInstance(processors[3], RasaDialogueProcessor)
        self.assertIs(processors[4], tts)
        self.assertIs(processors[5], transport.sink)
        self.assertIsInstance(processors[6], LLMAssistantAggregator)
        self.assertEqual(sum(p is tts for p in processors), 1)

    def test_existing_turn_aggregation_pair_can_be_retained(self):
        from pipecat.processors.aggregators.llm_context import LLMContext
        from pipecat.processors.aggregators.llm_response_universal import (
            LLMContextAggregatorPair,
        )

        transport = ExistingTransport()
        aggregator = LLMContextAggregatorPair(LLMContext())

        async def ask(text):
            raise AssertionError("Construction cannot make a dialogue request")

        pipeline = with_rasa(
            transport, FrameProcessor(), FrameProcessor(), ask, aggregator=aggregator
        )
        self.assertIs(pipeline.processors[3], aggregator.user())
        self.assertIs(pipeline.processors[7], aggregator.assistant())
