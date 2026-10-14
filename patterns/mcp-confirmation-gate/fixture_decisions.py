"""Fixed choices for repeatable local checks; not a language model."""
from mock_server import CANARY, DESCRIPTION
from rasa.shared.providers.llm.llm_response import LLMResponse, LLMToolCall


class Decisions:
    def __init__(self):
        self.stage = 0
        self.phase = 'read'
        self.resolved = False
        self.failures = []
        self.saw_description = False
        self.saw_result = False

    async def complete(self, client, messages, tools=None, model_settings=None):
        try:
            schemas = {item['function']['name']: item['function'] for item in tools or []}
            if set(schemas) == {'record_discovered_facts'}:
                return self.response('record_discovered_facts', {'facts': []})
            if not tools:
                return self.response(text='Please confirm the fictional recording.')
            if self.stage == 0:
                assert 'review_case' in schemas['activate']['parameters']['properties']['target_id']['enum']
                result = self.response('activate', {'target_id': 'review_case'})
            elif self.stage == 1:
                assert schemas['read_case']['description'] == DESCRIPTION
                self.saw_description = True
                result = self.response('read_case', {})
            elif self.stage == 2:
                assert CANARY in str(messages)
                self.saw_result = True
                result = self.response('record_local_canary', {'value': CANARY})
            elif self.phase == 'confirm' and not self.resolved:
                assert 'resolve_tool_confirmation' in schemas
                self.resolved = True
                result = self.response('resolve_tool_confirmation', {'confirmed': True})
            elif self.phase == 'read' and 'resolve_tool_confirmation' in schemas:
                result = self.response(text='Would you like me to record that fictional value?')
            else:
                result = self.response(text='Done with the fictional case.')
            if result.tool_calls:
                assert result.tool_calls[0].tool_name in schemas
            self.stage += 1
            return result
        except Exception as error:
            self.failures.append(str(error))
            raise

    def response(self, name=None, arguments=None, text=None):
        return LLMResponse(id=f'scripted-{self.stage}', choices=[text] if text else [],
            created=0, tool_calls=[LLMToolCall(id=f'call-{self.stage}',
                tool_name=name, tool_args=arguments or {})] if name else None)
