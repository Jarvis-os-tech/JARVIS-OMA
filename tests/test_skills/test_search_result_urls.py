"""Malformed provider links must not discard usable search results."""
import unittest
from unittest.mock import AsyncMock, patch

from connectors import internet_search as search


class SearchResultURLTests(unittest.IsolatedAsyncioTestCase):
    def test_rejects_bad_or_nonpublic_links(self):
        for value in ('https://[invalid', 'https://[::1', None, 123,
                      'file:///etc/passwd', 'http://localhost/',
                      'http://127.0.0.1/', 'https://user:password@example.com/'):
            with self.subTest(value=value):
                self.assertFalse(search._public_url(value))
        self.assertTrue(search._public_url('https://example.com/article'))

    async def test_bad_result_does_not_hide_later_valid_result(self):
        payload = {'web': {'results': [
            {'url': 'https://[invalid', 'title': 'Bad'},
            {'url': 'https://example.com/article', 'title': 'Useful',
             'description': 'Valid source'},
        ]}}
        with patch.object(search, '_get_json', new=AsyncMock(return_value=payload)):
            result = await search.brave_search('test query', api_key='synthetic')
        self.assertEqual([source['url'] for source in result['sources']],
                         ['https://example.com/article'])

    async def test_all_bad_results_return_normal_provider_error(self):
        payload = {'web': {'results': [{'url': 'https://[invalid'}]}}
        with patch.object(search, '_get_json', new=AsyncMock(return_value=payload)):
            with self.assertRaisesRegex(search.SearchProviderError, 'no usable results'):
                await search.brave_search('test query', api_key='synthetic')
