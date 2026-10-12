import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Config, load_config


class ConfigTests(unittest.TestCase):
    def test_default_config(self):
        cfg = load_config(path=None)
        self.assertEqual(cfg.agent.name, 'Jarvis')
        self.assertEqual(cfg.agent.voice, 'Aoede')
        self.assertEqual(cfg.agent.model, 'gemini-3.8-live')
        self.assertEqual(cfg.audio.input_sample_rate, 16000)
        self.assertEqual(cfg.audio.output_sample_rate, 24000)
        self.assertTrue(cfg.vad.enabled)
        self.assertTrue(cfg.skills.enabled)

    def test_env_overrides(self):
        env = {
            'JARVIS_AGENT_NAME': 'MyJarvis',
            'JARVIS_VOICE': 'Puck',
            'JARVIS_MODEL': 'gemini-2.5-live',
        }
        with patch.dict(os.environ, env):
            cfg = load_config(path=None)
            self.assertEqual(cfg.agent.name, 'MyJarvis')
            self.assertEqual(cfg.agent.voice, 'Puck')
            self.assertEqual(cfg.agent.model, 'gemini-2.5-live')

    def test_keyword_overrides(self):
        cfg = load_config(path=None, voice='Charon', agent_name='Assistant')
        self.assertEqual(cfg.agent.voice, 'Charon')
        self.assertEqual(cfg.agent.name, 'Assistant')

    def test_load_json_file(self):
        with tempfile.NamedTemporaryFile('w', suffix='.json', delete=False) as f:
            f.write('{"agent": {"name": "TestBot", "voice": "Fenrir"}, "skills": {"enabled": false}}')
            temp_path = f.name
        try:
            cfg = load_config(path=temp_path)
            self.assertEqual(cfg.agent.name, 'TestBot')
            self.assertEqual(cfg.agent.voice, 'Fenrir')
            self.assertFalse(cfg.skills.enabled)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_load_toml_file(self):
        with tempfile.NamedTemporaryFile('w', suffix='.toml', delete=False) as f:
            f.write('[agent]\nname = "TomlBot"\nvoice = "Kore"\n[audio]\ninput_sample_rate = 48000\n')
            temp_path = f.name
        try:
            cfg = load_config(path=temp_path)
            self.assertEqual(cfg.agent.name, 'TomlBot')
            self.assertEqual(cfg.agent.voice, 'Kore')
            self.assertEqual(cfg.audio.input_sample_rate, 48000)
        finally:
            Path(temp_path).unlink(missing_ok=True)

    def test_unsupported_format(self):
        with tempfile.NamedTemporaryFile('w', suffix='.yaml', delete=False) as f:
            f.write('agent: {name: YamlBot}')
            temp_path = f.name
        try:
            with self.assertRaises(ValueError) as ctx:
                load_config(path=temp_path)
            self.assertIn('Unsupported config file format', str(ctx.exception))
        finally:
            Path(temp_path).unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
