"""Native loader/config checks; no model, provider or bank network calls."""
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import socket

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("silverlake_deepgram_profile", HERE / "run_demo.py")
profile = importlib.util.module_from_spec(spec)
spec.loader.exec_module(profile)


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.guard = patch.object(socket.socket, "connect", side_effect=AssertionError("network_forbidden"))
        self.guard.start()
        self.addCleanup(self.guard.stop)

    def test_temporary_project_preserves_existing_bank_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            target = profile.prepare(directory)
            for relative in ("hooks.py", "skills/banking/skill.md", "skills/banking/tools.py"):
                self.assertEqual((target / relative).read_bytes(), (profile.BANK / relative).read_bytes())
            self.assertFalse((target / ".env").exists())
            self.assertFalse((target / ".venv").exists())

    def test_native_channel_resolves_only_deepgram(self):
        import yaml
        from rasa.mantle.config.channels import parse_channels, resolve_voice_channel_speech
        from rasa.core.channels.inspector import InspectorInputChannel
        config = yaml.safe_load((HERE / "integrations.yml").read_text())
        with patch.dict("os.environ", {"DEEPGRAM_API_KEY": "offline-placeholder"}):
            channels = resolve_voice_channel_speech(parse_channels(config["channels"]), model_groups=config["model_groups"])
        data = channels["inspector"]
        self.assertNotIn("speech_model", data)
        self.assertEqual(data["asr"]["provider"], "deepgram")
        self.assertEqual(data["tts"]["provider"], "deepgram")
        InspectorInputChannel.from_credentials(data)

    def test_native_agent_spec_uses_required_rc1_orchestrator(self):
        import yaml
        from rasa.mantle.config.agent_spec import agent_spec_from_config
        config = yaml.safe_load((HERE / "agent.yml").read_text())
        spec = agent_spec_from_config(config)
        self.assertEqual(spec.orchestrator.model_group, "orchestrator")
        self.assertNotIn("llm", config)

    def test_exact_runtime_and_source_lock(self):
        import importlib.metadata
        import tomllib
        self.assertEqual(importlib.metadata.version("rasa-pro"), "3.22.0rc1")
        locked = tomllib.loads((HERE / "uv.lock").read_text())
        rasa = next(p for p in locked["package"] if p["name"] == "rasa-pro")
        self.assertEqual(rasa["version"], "3.22.0rc1")
        self.assertEqual(rasa["wheels"][0]["hash"], "sha256:b05acc14b16a038f76fde95e06a22704be750aa10cbf2998a70fa5927db3dbcf")


if __name__ == "__main__":
    unittest.main()
