"""Opt-in voice custody and configured listener regression tests.
"""
import os
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import demo_launcher as demo
from demo_host import runtime_ports
from briefing.board_display import dashboard_html

class LocalVoiceTests(TestCase):
    def run_mode(self, voice):
        children = MagicMock()
        children.start.return_value.poll.return_value = None
        inspector = MagicMock(); inspector.poll.return_value = None
        supplied = {'RASA_LICENSE': 'synthetic-license', 'DEEPGRAM_API_KEY': 'synthetic-deepgram', 'OPENAI_API_KEY': 'synthetic-model'}
        def start(_children, env, mode):
            self.assertEqual(mode, 'scripted' if voice else 'live')
            return inspector, env
        with patch.object(demo, 'python_at', return_value=Path(sys.executable)), patch.object(demo, 'require_free_ports'), patch.object(demo, 'child_environment', return_value=supplied), patch.object(demo, 'Children', return_value=children), patch('demo_make.CheckoutControl'), patch.object(demo, 'completed') as completed, patch.object(demo, 'configure_native_sources'), patch.object(demo, 'wait_http'), patch.object(demo, 'start_inspector', side_effect=start) as launch, patch.object(demo.time, 'sleep', side_effect=KeyboardInterrupt), patch.object(demo.signal, 'signal'):
            demo.run_demo(voice=voice)
        for call in completed.call_args_list + children.start.call_args_list:
            self.assertNotIn('DEEPGRAM_API_KEY', call.kwargs['env'])
        env = launch.call_args.args[1]
        self.assertEqual(env.get('DEEPGRAM_API_KEY'), 'synthetic-deepgram' if voice else None)
        if voice:
            self.assertNotIn('OPENAI_API_KEY', env)
    def test_voice_key_only_reaches_inspector(self): self.run_mode(True)
    def test_normal_run_does_not_enable_voice_from_a_present_key(self): self.run_mode(False)
    def test_voice_requires_key_before_starting_any_child(self):
        with patch.object(demo, 'python_at', return_value=Path(sys.executable)), patch.object(demo, 'require_free_ports'), patch.object(demo, 'child_environment', return_value={'RASA_LICENSE':'synthetic'}), patch.object(demo.Children,'start') as start:
            with self.assertRaisesRegex(demo.DemoError, 'DEEPGRAM_API_KEY'): demo.run_demo(voice=True)
            start.assert_not_called()
    def test_configured_ports_reach_both_inspector_urls(self):
        with patch.dict(os.environ, {'BRIEFING_PAGE_PORT':'8960','BRIEFING_INSPECTOR_PORT':'5020'}, clear=True):
            self.assertEqual(runtime_ports(), (8960,5020))
            html=dashboard_html('127.0.0.1').decode()
            self.assertIn(':5020/webhooks/',html);self.assertIn('%3A5020',html)
            self.assertIn('allow="microphone; autoplay"',html);self.assertNotIn('5005',html)
    def test_invalid_ports_are_rejected(self):
        for a,b in [('0','5020'),('abc','5020'),('5020','5020'),('8960','65536')]:
            with patch.dict(os.environ, {'BRIEFING_PAGE_PORT':a,'BRIEFING_INSPECTOR_PORT':b}, clear=True):
                with self.assertRaises(ValueError):runtime_ports()
