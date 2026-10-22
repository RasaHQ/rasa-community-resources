"""Live managed model with explicitly constructed source fixtures.

This runs the real SDK-native model path, not live flight/weather providers.
Validated local source handlers still own every delivered card. The model's
output text never supplies card values or turns a failed source into success.
"""
from dataclasses import replace
import json

from briefing.native_runtime import native_turn
from briefing.replay import ReplayRunner


class LiveFixtureRunner(ReplayRunner):
    def __init__(self, client_factory, *, model, invoke=None):
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError('live_model_required')
        self.client_factory, self.model, self.invoke = client_factory, model, invoke

    def _run(self, work, inputs):
        answer = super()._run(work, inputs)
        # Carry source-validated data, never unchecked model prose, into a NEW
        # session for revisions. Partial weather updates retain the other data.
        prior = dict((work.inputs or {}).get('_prior_validated_brief', {}))
        for component, ref in answer.cards.items():
            data = ref.model_dump()
            prior[component] = {key: data[key] for key in
                                ('source', 'as_of', 'replay', 'payload', 'error') if key in data}
        return replace(answer, inputs={**(answer.inputs or {}), '_prior_validated_brief': prior})

    def _invoke(self, work, tools, handlers):
        prior = (work.inputs or {}).get('_prior_validated_brief', {})
        text = json.dumps({'request': work.text, 'prior_validated_brief': prior},
                          allow_nan=False, separators=(',', ':'))
        if len(text.encode()) > 64 * 1024:
            raise ValueError('prior_brief_limit')
        with self.client_factory() as client:
            return native_turn(client, agent={'model': self.model, 'tools': tools,
                'instructions': 'Use each offered source tool once. These are constructed REPLAY '
                                'fixtures, not live provider observations. Do not invent data. '
                                'Return a short completion message after the tool results.'},
                text=text, handlers=handlers, invoke=self.invoke)
