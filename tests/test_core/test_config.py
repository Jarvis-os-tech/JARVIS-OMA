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
        self.assertTrue(cfg.filesystem.enabled)
        self.assertTrue(cfg.filesystem.autonomous)
        self.assertTrue(cfg.filesystem.allow_delete)
        self.assertTrue(cfg.agent.single_sentence)
        self.assertTrue(cfg.audio.noise_suppression)
        self.assertEqual(cfg.audio.playback_cushion_s, 0.35)
        self.assertEqual(cfg.audio.mic_volume_percent, 80)
        self.assertEqual(cfg.vad.activity_handling, 'START_OF_ACTIVITY_INTERRUPTS')

    def test_filesystem_config_and_overrides(self):
        # Env override
        env = {
            'JARVIS_FS_AUTONOMOUS': 'false',
            'JARVIS_FS_ALLOW_DELETE': '0',
            'JARVIS_FS_MAX_READ_CHARS': '10000',
        }
        with patch.dict(os.environ, env):
            cfg = load_config(path=None)
            self.assertFalse(cfg.filesystem.autonomous)
            self.assertFalse(cfg.filesystem.allow_delete)
            self.assertEqual(cfg.filesystem.max_read_chars, 10000)

        # Keyword override
        cfg_kw = load_config(path=None, fs_autonomous=False, fs_allow_delete=False)
        self.assertFalse(cfg_kw.filesystem.autonomous)
        self.assertFalse(cfg_kw.filesystem.allow_delete)

        # TOML file load
        with tempfile.NamedTemporaryFile('w', suffix='.toml', delete=False) as f:
            f.write('[filesystem]\nautonomous = true\nallow_delete = false\nmax_read_chars = 25000\n')
            temp_path = f.name
        try:
            cfg_toml = load_config(path=temp_path)
            self.assertTrue(cfg_toml.filesystem.autonomous)
            self.assertFalse(cfg_toml.filesystem.allow_delete)
            self.assertEqual(cfg_toml.filesystem.max_read_chars, 25000)
        finally:
            Path(temp_path).unlink(missing_ok=True)

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


    def test_greeting_config_and_overrides(self):
        # Default
        cfg = load_config(path=None)
        self.assertTrue(cfg.agent.greet_on_activation)
        self.assertIsNone(cfg.agent.greeting_prompt)

        # Env overrides
        env = {
            'JARVIS_GREET_ON_ACTIVATION': 'false',
            'JARVIS_GREETING_PROMPT': 'Hello boss',
        }
        with patch.dict(os.environ, env):
            cfg_env = load_config(path=None)
            self.assertFalse(cfg_env.agent.greet_on_activation)
            self.assertEqual(cfg_env.agent.greeting_prompt, 'Hello boss')

        # Keyword overrides
        cfg_kw = load_config(path=None, greet_on_activation=False, greeting_prompt='Custom prompt')
        self.assertFalse(cfg_kw.agent.greet_on_activation)
        self.assertEqual(cfg_kw.agent.greeting_prompt, 'Custom prompt')

        # TOML load
        with tempfile.NamedTemporaryFile('w', suffix='.toml', delete=False) as f:
            f.write('[agent]\ngreet_on_activation = false\ngreeting_prompt = "Online and ready."\n')
            temp_path = f.name
        try:
            cfg_toml = load_config(path=temp_path)
            self.assertFalse(cfg_toml.agent.greet_on_activation)
            self.assertEqual(cfg_toml.agent.greeting_prompt, 'Online and ready.')
        finally:
            Path(temp_path).unlink(missing_ok=True)


    def test_single_sentence_and_audio_tuning_overrides(self):
        env = {
            'JARVIS_SINGLE_SENTENCE': 'false',
            'JARVIS_NOISE_SUPPRESSION': 'false',
            'JARVIS_MIC_VOLUME_PERCENT': '90',
            'JARVIS_PLAYBACK_CUSHION_S': '0.5',
            'JARVIS_NO_INTERRUPT': 'true',
        }
        with patch.dict(os.environ, env):
            cfg = load_config(path=None)
            self.assertFalse(cfg.agent.single_sentence)
            self.assertFalse(cfg.audio.noise_suppression)
            self.assertEqual(cfg.audio.mic_volume_percent, 90)
            self.assertEqual(cfg.audio.playback_cushion_s, 0.5)
            self.assertEqual(cfg.vad.activity_handling, 'NO_INTERRUPTION')

        # Keyword override
        cfg_kw = load_config(path=None, no_interrupt=True, single_sentence=False)
        self.assertFalse(cfg_kw.agent.single_sentence)
        self.assertEqual(cfg_kw.vad.activity_handling, 'NO_INTERRUPTION')


if __name__ == '__main__':
    unittest.main()
