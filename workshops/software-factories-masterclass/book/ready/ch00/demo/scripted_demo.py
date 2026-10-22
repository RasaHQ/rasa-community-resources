"""Print the checked keyless Mantle conversation; never call a real model."""
from contextlib import redirect_stderr, redirect_stdout
import io
import os
from pathlib import Path
import runpy
import sys
import unittest


def main() -> int:
    os.environ['LITELLM_MODE'] = 'PRODUCTION'
    transcript = []
    diagnostics = io.StringIO()
    # Keep engine diagnostics out of the projected transcript. In particular,
    # this is not a request/tool-argument trace or a saved credential log.
    with redirect_stdout(diagnostics), redirect_stderr(diagnostics):
        module = runpy.run_path(str(Path(__file__).parent / 'tests' /
                                    'test_mantle_conversation.py'))
        if not module['HAS_MANTLE']:
            print('Use the managed project interpreter.', file=sys.__stderr__)
            return 2
        case = module['ScriptedMantleConversation'](
            'test_scripted_provider_drives_real_engine_mcp_and_cards')
        case.transcript_sink = transcript
        result = unittest.TextTestRunner(stream=diagnostics).run(
            unittest.TestSuite([case]))
    if not result.wasSuccessful() or result.skipped or len(transcript) != 10:
        print('SCRIPTED REPLAY FAILED: the checked ten-turn conversation did not '
              'complete. No successful demo transcript is claimed.', file=sys.stderr)
        return 1
    print('SCRIPTED / CONSTRUCTED REPLAY — no real model or live provider')
    print('Actual Mantle orchestration, MCP, Core and delivered text cards. '
          'Responses and capability selection are scripted, not model reasoning.\n')
    for number, (request, delivered) in enumerate(transcript, 1):
        print(f'Turn {number} — scripted user: {request}')
        print(f'Mantle delivered:\n{delivered}\n')
    print('Completed 10 checked scripted turns. Real-model behavior, voice and '
          'live providers were not exercised.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
