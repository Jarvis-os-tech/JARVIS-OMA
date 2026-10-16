import json
import unittest
from unittest.mock import Mock, patch

from jarvis_memory.embeddings import (
    DeterministicFakeEmbeddingProvider,
    EmbeddingError,
    GeminiEmbeddingProvider,
    OllamaEmbeddingProvider,
    StaticEmbeddingProvider,
)


class Response:
    def __init__(self, value):
        self.data = value if isinstance(value, bytes) else json.dumps(value).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, size):
        return self.data[:size]


class EmbeddingTests(unittest.TestCase):
    def provider(self, responses, **kwargs):
        opener = Mock()
        opener.open.side_effect = [Response(value) for value in responses]
        return OllamaEmbeddingProvider("http://127.0.0.1:11434", "tiny", 3,
                                       opener=opener, **kwargs), opener

    def test_embed_endpoint_batches_and_tracks_status(self):
        provider, opener = self.provider([{"embeddings": [[1, 2.5, -3], [4, 5, 6]]}])
        self.assertEqual(provider.status()["state"], "unknown")
        self.assertEqual(provider.embed_texts(["one", "two"]), [[1.0, 2.5, -3.0], [4.0, 5.0, 6.0]])
        request = opener.open.call_args.args[0]
        self.assertEqual(json.loads(request.data), {"model": "tiny", "input": ["one", "two"], "truncate": False})
        self.assertEqual(provider.identity, "ollama:tiny:3")
        self.assertTrue(provider.status()["available"])

    def test_legacy_endpoint_uses_one_request_per_text(self):
        provider, opener = self.provider([{"embedding": [1, 2, 3]}, {"embedding": [4, 5, 6]}],
                                         endpoint="embeddings")
        self.assertEqual(provider.embed_texts(["a", "b"]), [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]])
        self.assertEqual(opener.open.call_count, 2)

    def test_ssrf_urls_are_rejected(self):
        bad = ["https://localhost:11434", "http://example.com", "http://127.0.0.2:11434",
               "http://user@localhost:11434", "http://localhost:11434@evil.test",
               "http://localhost:11434/api/embed?next=http://evil.test", "http://[::2]:11434"]
        for url in bad:
            with self.subTest(url=url), self.assertRaises(ValueError):
                OllamaEmbeddingProvider(url, "m", 2)

    def test_proxy_disabled_and_redirect_handler_installed(self):
        with patch("jarvis_memory.embeddings.build_opener") as build:
            OllamaEmbeddingProvider("http://localhost:11434/api/embed", "m", 2)
        handlers = build.call_args.args
        self.assertEqual(handlers[0].proxies, {})
        self.assertIsNone(handlers[1].redirect_request(None, None, 302, "", {}, "http://evil.test"))

    def test_malformed_dimensions_nan_and_counts_fail_closed(self):
        malformed = [
            {"embeddings": [[1, 2]]},
            {"embeddings": [[1, 2, float("nan")]]},
            {"embeddings": [[1, 2, True]]},
            {"embeddings": []},
            [],
            b"not-json",
        ]
        for response in malformed:
            with self.subTest(response=response):
                provider, _ = self.provider([response])
                with self.assertRaises(EmbeddingError):
                    provider.embed_texts(["x"])
                self.assertEqual(provider.status()["state"], "unavailable")

    def test_input_request_and_response_limits(self):
        provider, opener = self.provider([], max_text_chars=3, max_batch_size=1)
        for texts in (["long"], ["a", "b"]):
            with self.subTest(texts=texts), self.assertRaises(EmbeddingError):
                provider.embed_texts(texts)
        self.assertFalse(opener.open.called)
        provider, _ = self.provider([], max_request_bytes=10)
        with self.assertRaisesRegex(EmbeddingError, "request exceeds"):
            provider.embed_texts(["x"])
        provider, _ = self.provider([b"x" * 101], max_response_bytes=100)
        with self.assertRaisesRegex(EmbeddingError, "response exceeds"):
            provider.embed_texts(["x"])

    def test_empty_batch_never_calls_network(self):
        provider, opener = self.provider([])
        self.assertEqual(provider.embed_texts([]), [])
        opener.open.assert_not_called()

    def test_gemini_batch_uses_api_key_and_requested_dimension(self):
        opener = Mock()
        opener.open.return_value = Response({"embeddings": [
            {"values": [1.0] * 128}, {"values": [2.0] * 128}]})
        provider = GeminiEmbeddingProvider("secret-key", "gemini-embedding-2", 128, opener=opener)
        self.assertEqual(provider.embed_texts(["one", "two"]), [[1.0] * 128, [2.0] * 128])
        request = opener.open.call_args.args[0]
        self.assertEqual(request.get_header("X-goog-api-key"), "secret-key")
        payload = json.loads(request.data)
        self.assertEqual(len(payload["requests"]), 2)
        self.assertEqual(payload["requests"][0]["outputDimensionality"], 128)
        self.assertNotIn("secret-key", request.data.decode())
        self.assertEqual(provider.identity, "gemini:gemini-embedding-2:128")

    def test_gemini_missing_key_degrades_without_network(self):
        opener = Mock()
        provider = GeminiEmbeddingProvider("", "gemini-embedding-2", 768, opener=opener)
        with self.assertRaisesRegex(EmbeddingError, "API key"):
            provider.embed_texts(["private memory"])
        opener.open.assert_not_called()

    def test_static_and_fake_are_deterministic_and_not_semantic(self):
        static = StaticEmbeddingProvider({"x": [1, 0]}, 2)
        self.assertEqual(static.embed_texts(["x"]), [[1.0, 0.0]])
        self.assertFalse(static.status()["semantic"])
        with self.assertRaises(EmbeddingError):
            static.embed_texts(["missing"])
        fake = DeterministicFakeEmbeddingProvider(4)
        self.assertEqual(fake.embed_texts(["same"]), fake.embed_texts(["same"]))
        self.assertFalse(fake.status()["semantic"])


if __name__ == "__main__":
    unittest.main()
