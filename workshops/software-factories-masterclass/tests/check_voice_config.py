"""Offline voice regression check. Run with the workshop Mantle interpreter."""
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import yaml
from pydantic import TypeAdapter
from rasa.core.channels.voice_stream.asr import BUILT_IN_ASR_ENGINES
from rasa.core.channels.voice_stream.asr.deepgram.config import DeepgramASRConfig
from rasa.core.channels.voice_stream.tts.deepgram import DeepgramTTSConfig
from rasa.mantle.validation import collect_project_findings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from factory.build import generate

with TemporaryDirectory() as directory:
    projects = [ROOT / "studio", ROOT / "reference/finished-agent"]
    for spec in ("starter", "full"):
        project = Path(directory) / spec
        generate((ROOT / "reference" / (spec + ".json")).read_bytes(), project)
        projects.append(project)
    for project in projects:
        assert not collect_project_findings(project)
        config = yaml.safe_load((project / "integrations.yml").read_text())["channels"]["inspector"]
        recognition = dict(config["asr"])
        assert recognition.pop("name") in BUILT_IN_ASR_ENGINES
        assert TypeAdapter(DeepgramASRConfig).validate_python(recognition).version == "v2"
        speech = dict(config["tts"])
        assert speech.pop("name") == "deepgram"
        assert DeepgramTTSConfig.model_validate(speech).language_map["en"].model == "aura-2-andromeda-en"
        print("PASS voice configuration:", project.name)
