# concern: ops
"""Start a version's unchanged server.py on Deepgram instead of Speechmatics.

    cd langgraph && uv run --locked python ../shared/speech-deepgram/launch.py server.py --port 5006

The LangGraph and Strands servers import ``SpeechmaticsASR`` and
``SpeechmaticsTTS`` from ``cedar_speech``. This puts ``DeepgramASR`` and
``DeepgramTTS`` under those names before the server is imported, then runs it
as ``__main__``. The voice loop, the agent and the guard are the shipped
files, byte for byte; only the vendor client differs.
"""

import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path.cwd()))

import cedar_speech  # noqa: E402

from cedar_speech_deepgram import DeepgramASR, DeepgramTTS  # noqa: E402

cedar_speech.SpeechmaticsASR = DeepgramASR
cedar_speech.SpeechmaticsTTS = DeepgramTTS

if __name__ == "__main__":
    script, sys.argv = sys.argv[1], sys.argv[1:]
    print(f"launch.py: {script} with cedar_speech_deepgram (DeepgramASR, DeepgramTTS)", flush=True)
    runpy.run_path(script, run_name="__main__")
