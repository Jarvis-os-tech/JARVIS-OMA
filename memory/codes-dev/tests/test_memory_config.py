import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from config import Config, MemoryConfig, load_config


class MemoryConfigTests(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {}, clear=True)
        self.env.start()
        self.addCleanup(self.env.stop)
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'config.json'

    def load(self, memory):
        self.path.write_text(json.dumps({'memory': memory}), encoding='utf-8')
        return load_config(self.path)

    def test_defaults_and_independent_instances(self):
        self.assertEqual(load_config(self.path).memory, MemoryConfig())
        self.assertEqual(MemoryConfig(), MemoryConfig(True, '', 1000, 6000, True, False, '', 'http://127.0.0.1:11434'))
        first, second = Config(), Config()
        first.memory.enabled = False
        self.assertTrue(second.memory.enabled)

    def test_load_all_fields(self):
        values = dict(enabled=False, path='/tmp/memory', max_facts=20,
                      context_max_chars=500, record_sessions=True,
                      auto_capture=True, extraction_model='local-model',
                      extraction_url='http://localhost:11434')
        self.assertEqual(self.load(values).memory, MemoryConfig(**values))

    def test_example_toml(self):
        example = Path(__file__).resolve().parents[2] / 'config.toml.example'
        self.path = Path(self.directory.name) / 'config.toml'
        self.path.write_text(example.read_text(encoding='utf-8'), encoding='utf-8')
        self.assertEqual(load_config(self.path).memory, MemoryConfig())

    def test_environment_precedence_and_boolean_values(self):
        for value, expected in [('true', True), ('1', True), ('yes', True),
                                ('false', False), ('0', False), ('no', False)]:
            with self.subTest(value=value), patch.dict(os.environ, {
                'JARVIS_MEMORY_ENABLED': value,
                'JARVIS_MEMORY_PATH': '/tmp/env-memory',
            }):
                memory = self.load({'enabled': not expected, 'path': '/tmp/file-memory'}).memory
                self.assertEqual(memory.enabled, expected)
                self.assertEqual(memory.path, '/tmp/env-memory')
        with patch.dict(os.environ, {'JARVIS_MEMORY_ENABLED': 'maybe'}):
            with self.assertRaisesRegex(ValueError, 'JARVIS_MEMORY_ENABLED'):
                load_config(self.path)

    def test_invalid_field_types_and_limits(self):
        cases = [('enabled', 'false'), ('record_sessions', 1), ('auto_capture', 'true'),
                 ('structured_capture', 'true'), ('semantic_retrieval', 1),
                 ('path', None), ('extraction_model', 1), ('extraction_url', False)]
        cases += [(name, value) for name in ('max_facts', 'context_max_chars')
                  for value in (0, -1, True, 1.5, '100')]
        for name, value in cases:
            with self.subTest(name=name, value=value):
                with self.assertRaisesRegex(ValueError, 'memory.' + name):
                    self.load({name: value})
        with self.assertRaisesRegex(ValueError, 'mapping'):
            self.load([])

    def test_auto_capture_requires_model(self):
        for model in ('', '   '):
            with self.subTest(model=model):
                with self.assertRaisesRegex(ValueError, 'requires a nonempty'):
                    self.load({'auto_capture': True, 'extraction_model': model})
        self.assertFalse(self.load({'extraction_model': ''}).memory.auto_capture)

    def test_semantic_retrieval_requires_valid_local_configuration(self):
        with self.assertRaisesRegex(ValueError, 'semantic_model'):
            self.load({'semantic_retrieval': True})
        with self.assertRaisesRegex(ValueError, 'semantic_provider'):
            self.load({'semantic_provider': 'cloud'})
        for value in (-0.1, 1.1, True, '0.5'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'semantic_min_score'):
                self.load({'semantic_min_score': value})
        for value in (0, 65537, True, 1.5, '768'):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'semantic_dimension'):
                self.load({'semantic_dimension': value})
        config = self.load({'semantic_retrieval': True, 'semantic_model': 'local-embed'})
        self.assertTrue(config.memory.semantic_retrieval)

    def test_obsidian_timezone_validation(self):
        for value in ('Invalid/Timezone', '', 1):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'memory.obsidian_timezone'):
                self.load({'obsidian_timezone': value})
        self.assertEqual(self.load({'obsidian_timezone': 'UTC'}).memory.obsidian_timezone, 'UTC')

    def test_manifest_contract(self):
        root = Path(__file__).resolve().parents[2]
        manifest = root / 'skills' / 'manifests' / 'memory.json'
        if not manifest.is_file():
            manifest = root / 'skill_manifests' / 'memory.json'
        skills = json.loads(manifest.read_text(encoding='utf-8'))['skills']
        self.assertEqual({item['adapter'] for item in skills}, {
            'memory.remember', 'memory.recall', 'memory.forget', 'memory.clear',
            'memory.profile', 'memory.index', 'memory.status', 'memory.obsidian',
            'memory.correct', 'memory.history'})
        self.assertEqual(len(skills), 10)
        by_name = {item['name']: item['parameters_json_schema'] for item in skills}
        self.assertEqual(by_name['recall_memory']['required'], [])
        self.assertEqual(by_name['recall_memory']['properties']['limit'],
                         {'type': 'integer', 'minimum': 1, 'maximum': 50})
        self.assertEqual(by_name['update_memory_profile']['properties']['name']['enum'],
                         ['SOUL', 'MEMORY', 'USER'])
        for schema in by_name.values():
            self.assertFalse(schema['additionalProperties'])
            for prop in schema['properties'].values():
                self.assertIn(prop['type'], ('string', 'integer', 'boolean'))


if __name__ == '__main__':
    unittest.main()
