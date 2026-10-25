import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Config, load_config


class ConfigTests(unittest.TestCase):
    def test_native_webrtc_gain_requires_native_backend_and_boolean_settings(self):
        cfg = Config()
        cfg.audio.native_webrtc_gain = True
        with self.assertRaisesRegex(ValueError, 'requires the native backend'):
            cfg.validate()
        cfg.audio.backend = 'native'
        cfg.validate()
        for name in ('native_webrtc_gain', 'start_muted'):
            for invalid in ('true', 1, None):
                with self.subTest(name=name, invalid=invalid):
                    candidate = Config()
                    setattr(candidate.audio, name, invalid)
                    with self.assertRaisesRegex(ValueError, 'must be a boolean'):
                        candidate.validate()

    def test_native_gain_and_start_mute_environment_override_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[audio]\nbackend = "native"\nnative_webrtc_gain = false\nstart_muted = false\n')
            with patch.dict(os.environ, {'JARVIS_NATIVE_WEBRTC_GAIN': 'true',
                                         'JARVIS_START_MUTED': 'true'}):
                cfg = load_config(path)
            self.assertTrue(cfg.audio.native_webrtc_gain)
            self.assertTrue(cfg.audio.start_muted)

    @patch('config._find_config_file', return_value=None)
    def test_default_config(self, _mock_find):
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
        self.assertFalse(cfg.agent.single_sentence)
        self.assertTrue(cfg.audio.noise_suppression)
        self.assertTrue(cfg.audio.local_barge_in)
        self.assertFalse(cfg.audio.diagnostic_transcripts)
        self.assertEqual(cfg.audio.playback_cushion_s, 0.32)
        self.assertEqual(cfg.audio.mic_volume_percent, 55)
        self.assertEqual(cfg.vad.activity_handling, 'START_OF_ACTIVITY_INTERRUPTS')
        self.assertTrue(cfg.standby.enabled)
        self.assertEqual(cfg.standby.threshold, 0.05)
        self.assertEqual(cfg.standby.vad_threshold, 0.0)

    def test_standby_config_loads_and_validates(self):
        with tempfile.NamedTemporaryFile('w', suffix='.toml', delete=False) as f:
            f.write('[standby]\nenabled = true\nthreshold = 0.7\nvad_threshold = 0.4\n')
            temp_path = f.name
        try:
            cfg = load_config(path=temp_path)
            self.assertEqual(cfg.standby.threshold, 0.7)
            self.assertEqual(cfg.standby.vad_threshold, 0.4)
        finally:
            Path(temp_path).unlink(missing_ok=True)

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

    def test_invalid_audio_is_rejected_before_engine_startup(self):
        cases = {
            'input_frame_ms': [0, -20, 20.5, True, '20'],
            'output_frame_ms': [0, -20],
            'input_sample_rate': [0, 4000, 16000.5],
            'output_sample_rate': [48000, 16000],
            'duck_gain': [-0.1, 1.1, float('nan'), float('inf'), True],
            'voice_band_ratio': [-0.1, 1.1],
            'playback_cushion_s': [-1, float('inf')],
            'noise_suppression': ['false', 1],
            'mic_volume_percent': [0, 101, '80'],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    config = Config()
                    setattr(config.audio, name, value)
                    with self.assertRaisesRegex(ValueError, f'audio.{name}'):
                        config.validate()

    def test_invalid_root_settings_and_sections_are_rejected(self):
        for section, name, value in [('agent', 'model', ''), ('agent', 'voice', 7),
                                     ('skills', 'enabled', 'false')]:
            with self.subTest(section=section, name=name):
                config = Config()
                setattr(getattr(config, section), name, value)
                with self.assertRaisesRegex(ValueError, f'{section}.{name}'):
                    config.validate()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            for section in ('audio', 'vad', 'skills'):
                path.write_text('{"' + section + '": []}')
                with self.subTest(section=section):
                    with self.assertRaisesRegex(ValueError, f'{section} section must be a mapping'):
                        load_config(path)

    def test_audio_frame_and_interruption_settings_are_coherent(self):
        config = Config()
        config.audio.input_sample_rate = 11025
        with self.assertRaisesRegex(ValueError, 'integral number of samples'):
            config.validate()
        config.audio.input_frame_ms = 40
        config.validate()
        config.audio.barge_in_after_ms = config.audio.duck_after_ms
        with self.assertRaisesRegex(ValueError, 'barge_in_after_ms'):
            config.validate()

    def test_invalid_vad_settings_fail_locally(self):
        cases = {
            'enabled': [False, 'true'],
            'start_sensitivity': ['invalid'],
            'end_sensitivity': ['START_SENSITIVITY_HIGH'],
            'activity_handling': ['invalid'],
            'prefix_padding_ms': [-1, True],
            'silence_duration_ms': [0, '300'],
        }
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    config = Config()
                    setattr(config.vad, name, value)
                    with self.assertRaisesRegex(ValueError, f'vad.{name}'):
                        config.validate()

    def test_toml_fractional_frame_duration_is_not_silently_truncated(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.toml'
            path.write_text('[audio]\ninput_frame_ms = 20.5\n')
            with self.assertRaisesRegex(ValueError, 'audio.input_frame_ms'):
                load_config(path)

    def test_environment_types_are_independent_of_replaced_file_value(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'config.json'
            path.write_text('{"audio": {"mic_volume_percent": null, "noise_suppression": "invalid"}}')
            with patch.dict(os.environ, {'JARVIS_MIC_VOLUME_PERCENT': '90',
                                         'JARVIS_NOISE_SUPPRESSION': 'false'}):
                config = load_config(path)
            self.assertEqual(config.audio.mic_volume_percent, 90)
            self.assertIs(config.audio.noise_suppression, False)

    @patch('config._find_config_file', return_value=None)
    def test_invalid_audio_environment_override_is_not_silently_ignored(self, _mock_find):
        for key, value in [('JARVIS_MIC_VOLUME_PERCENT', 'loud'),
                           ('JARVIS_NOISE_SUPPRESSION', 'maybe'),
                           ('JARVIS_NATIVE_WEBRTC_GAIN', 'maybe'),
                           ('JARVIS_START_MUTED', 'maybe'),
                           ('JARVIS_PLAYBACK_CUSHION_S', 'nan')]:
            with self.subTest(key=key), patch.dict(os.environ, {key: value}):
                with self.assertRaises(ValueError):
                    load_config()

    @patch('config._find_config_file', return_value=None)
    def test_model_environment_alias_has_lower_priority(self, _mock_find):
        with patch.dict(os.environ, {'GEMINI_LIVE_MODEL': 'legacy-model',
                                     'JARVIS_MODEL': 'preferred-model'}):
            self.assertEqual(load_config().agent.model, 'preferred-model')
            self.assertEqual(load_config(model='cli-model').agent.model, 'cli-model')
        with patch.dict(os.environ, {'GEMINI_LIVE_MODEL': 'legacy-model'}, clear=True):
            self.assertEqual(load_config().agent.model, 'legacy-model')


if __name__ == '__main__':
    unittest.main()
