"""Launch rasa inspect with the project .env loaded."""

from __future__ import annotations

import os
import sys

from dotenv import load_dotenv

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
os.chdir(PROJECT_ROOT)

sys.exit(os.system(f'"{sys.executable}" -m rasa inspect'))
