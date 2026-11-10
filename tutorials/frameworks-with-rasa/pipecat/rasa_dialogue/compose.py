"""Insert the dialogue processor into an existing Pipecat speech stack."""

from pipecat.pipeline.pipeline import Pipeline
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from rasa_dialogue.processor import RasaDialogueProcessor


def with_rasa(transport, stt, tts, ask, *, aggregator=None):
    if aggregator is None:
        aggregator = LLMContextAggregatorPair(
            LLMContext(), user_params=LLMUserAggregatorParams(empty_user_turn=None)
        )
    return Pipeline(
        [
            transport.input(),
            stt,
            aggregator.user(),
            RasaDialogueProcessor(ask),
            tts,
            transport.output(),
            aggregator.assistant(),
        ]
    )
