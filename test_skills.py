"""Offline tests for dynamic Omarchy skill discovery and policy adapters."""
import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from skills import DesktopSkills, SkillError


def manifest(skills):
    return {'version': 1, 'skills': skills}


def spec(name='apps', adapter='applications.list', properties=None, required=None):
    return {
        'name': name,
        'description': 'Test dynamic skill.',
        'adapter': adapter,
        'parameters_json_schema': {
            'type': 'object', 'properties': properties or {},
            'required': required or [], 'additionalProperties': False,
        },
    }


class DynamicManifestTests(unittest.IsolatedAsyncioTestCase):
    def make_skills(self, *documents):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        for index, document in enumerate(documents):
            (directory / f'{index}.json').write_text(json.dumps(document), encoding='utf-8')
        return DesktopSkills([directory])

    async def test_discovers_skill_names_and_schemas_from_manifests(self):
        skills = self.make_skills(manifest([spec('second'), spec('first')]))
        self.assertEqual([item['name'] for item in skills.declarations], ['second', 'first'])
        self.assertFalse(skills.declarations[0]['parameters_json_schema']['additionalProperties'])

    async def test_duplicate_dynamic_names_fail_closed(self):
        with self.assertRaisesRegex(SkillError, 'duplicate'):
            self.make_skills(manifest([spec('same')]), manifest([spec('same')]))

    async def test_unknown_adapter_and_malformed_schema_fail_closed(self):
        with self.assertRaisesRegex(SkillError, 'unapproved adapter'):
            self.make_skills(manifest([spec(adapter='shell.command')]))
        bad = spec()
        bad['parameters_json_schema']['additionalProperties'] = True
        with self.assertRaisesRegex(SkillError, 'strict object'):
            self.make_skills(manifest([bad]))

    async def test_runtime_schema_rejects_extra_wrong_and_boolean_integer_args(self):
        integer = {'type': 'integer', 'minimum': 1, 'maximum': 10}
        skills = self.make_skills(manifest([
            spec('brightness', 'display.brightness',
                 {'direction': {'type': 'string', 'enum': ['raise', 'lower']},
                  'amount': integer}, ['direction', 'amount'])]))
        for args in (
            {'direction': 'raise'},
            {'direction': 'sideways', 'amount': 2},
            {'direction': 'raise', 'amount': True},
            {'direction': 'raise', 'amount': 11},
            {'direction': 'raise', 'amount': 2, 'extra': 'no'},
        ):
            with self.subTest(args=args), self.assertRaisesRegex(SkillError, 'invalid arguments'):
                await skills.execute('brightness', args)

    async def test_dynamic_name_routes_to_reviewed_adapter(self):
        skills = self.make_skills(manifest([
            spec('make_it_brighter', 'display.brightness',
                 {'direction': {'type': 'string', 'enum': ['raise', 'lower']},
                  'amount': {'type': 'integer', 'minimum': 1, 'maximum': 25}},
                 ['direction'])]))
        skills._run = AsyncMock(return_value='')
        result = await skills.execute('make_it_brighter', {'direction': 'raise', 'amount': 7})
        self.assertEqual(result['amount'], 7)
        skills._run.assert_awaited_once_with(
            skills._commands['omarchy-brightness-display'], '+7%')

    async def test_url_adapter_rejects_unsafe_schemes_and_credentials(self):
        skills = DesktopSkills()
        for url in ('file:///etc/passwd', 'javascript:alert(1)',
                    'https://user:secret@example.com/', 'http://127.0.0.1/admin',
                    'http://[::1]/', 'https://localhost/private'):
            with self.subTest(url=url), self.assertRaises(SkillError):
                await skills.execute('open_website', {'url': url})

    async def test_application_adapter_launches_only_catalogued_exact_match(self):
        skills = DesktopSkills()
        with patch.object(skills, '_applications', return_value={'firefox.desktop': 'Firefox'}), \
             patch.object(skills, '_launch', new=AsyncMock()) as launch:
            result = await skills.execute('open_application', {'name': 'Firefox'})
            self.assertEqual(result['application'], 'Firefox')
            launch.assert_awaited_once_with(skills._commands['gtk-launch'], 'firefox.desktop')
            with self.assertRaises(SkillError):
                await skills.execute('open_application', {'name': 'firefox; shutdown'})


if __name__ == '__main__':
    unittest.main()
