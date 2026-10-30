"""Small, defensive embedding providers for local memory retrieval.

Only loopback Ollama HTTP endpoints are supported.  The transport deliberately
ignores proxy environment variables and refuses redirects, while response
validation prevents malformed or non-finite vectors entering an index.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from hashlib import sha256
import json
import math
from typing import Mapping, Sequence
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


class EmbeddingError(RuntimeError):
    """An embedding provider was unavailable or returned unsafe data."""


class EmbeddingProvider(ABC):
    """Synchronous interface used by the memory retrieval layer."""

    @property
    @abstractmethod
    def identity(self) -> str:
        """Stable identity including provider, model, and vector dimension."""

    @abstractmethod
    def status(self) -> dict:
        """Return local provider state without making a network request."""

    @abstractmethod
    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Embed texts in order, or raise :class:`EmbeddingError`."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: D401
        """Reject redirects so a local server cannot redirect off-loopback."""
        return None


def _vector(value, dimension: int) -> list[float]:
    if not isinstance(value, list) or len(value) != dimension:
        raise EmbeddingError(f"embedding must contain exactly {dimension} values")
    result = []
    for number in value:
        if isinstance(number, bool) or not isinstance(number, (int, float)):
            raise EmbeddingError("embedding values must be numbers")
        number = float(number)
        if not math.isfinite(number):
            raise EmbeddingError("embedding values must be finite")
        result.append(number)
    return result


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Bounded client for Ollama's ``/api/embed`` or legacy endpoint."""

    _HOSTS = frozenset(("localhost", "127.0.0.1", "::1"))

    def __init__(self, base_url: str, model: str, dimension: int, *,
                 endpoint: str = "embed", timeout: float = 10.0,
                 max_text_chars: int = 8192, max_batch_size: int = 32,
                 max_request_bytes: int = 262144, max_response_bytes: int = 4194304,
                 opener=None) -> None:
        if endpoint not in ("embed", "embeddings"):
            raise ValueError("endpoint must be 'embed' or 'embeddings'")
        if not isinstance(base_url, str):
            raise ValueError("Ollama URL must be a string")
        parsed = urlsplit(base_url)
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError("Ollama URL has an invalid port") from exc
        if (parsed.scheme != "http" or parsed.hostname not in self._HOSTS
                or parsed.username is not None or parsed.password is not None
                or parsed.query or parsed.fragment):
            raise ValueError("Ollama embeddings require a local loopback HTTP URL")
        supplied_path = parsed.path.rstrip("/")
        if supplied_path not in ("", "/api/embed", "/api/embeddings"):
            raise ValueError("Ollama URL path must be /api/embed or /api/embeddings")
        if supplied_path:
            endpoint = supplied_path.rsplit("/", 1)[-1]
        if not isinstance(model, str) or not model.strip() or len(model) > 200 or "\x00" in model:
            raise ValueError("model must be a nonempty string of at most 200 characters")
        if type(dimension) is not int or not 1 <= dimension <= 65536:
            raise ValueError("dimension must be between 1 and 65536")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not math.isfinite(timeout) or not 0 < timeout <= 30:
            raise ValueError("timeout must be greater than 0 and at most 30 seconds")
        for name, value, maximum in (
            ("max_text_chars", max_text_chars, 100000),
            ("max_batch_size", max_batch_size, 256),
            ("max_request_bytes", max_request_bytes, 8388608),
            ("max_response_bytes", max_response_bytes, 67108864),
        ):
            if type(value) is not int or not 1 <= value <= maximum:
                raise ValueError(f"{name} must be between 1 and {maximum}")
        host = f"[{parsed.hostname}]" if parsed.hostname == "::1" else parsed.hostname
        authority = host + (f":{port}" if port is not None else "")
        self.url = f"http://{authority}/api/{endpoint}"
        self.model = model.strip()
        self.dimension = dimension
        self.endpoint = endpoint
        self.timeout = float(timeout)
        self.max_text_chars = max_text_chars
        self.max_batch_size = max_batch_size
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self._opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())
        self._state = "unknown"
        self._last_error = None

    @property
    def identity(self) -> str:
        return f"ollama:{self.model}:{self.dimension}"

    def status(self) -> dict:
        return {"identity": self.identity, "state": self._state,
                "available": self._state == "available", "last_error": self._last_error,
                "endpoint": self.endpoint, "semantic": True}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise EmbeddingError("texts must be a list")
        if not texts:
            return []
        if len(texts) > self.max_batch_size:
            raise EmbeddingError(f"embedding batch exceeds {self.max_batch_size} texts")
        if any(not isinstance(text, str) or len(text) > self.max_text_chars for text in texts):
            raise EmbeddingError(f"each text must be a string of at most {self.max_text_chars} characters")
        try:
            if self.endpoint == "embed":
                vectors = self._request({"model": self.model, "input": texts, "truncate": False})
                raw = vectors.get("embeddings") if isinstance(vectors, dict) else None
                if not isinstance(raw, list) or len(raw) != len(texts):
                    raise EmbeddingError("Ollama response has the wrong embedding count")
                result = [_vector(item, self.dimension) for item in raw]
            else:
                result = []
                for text in texts:
                    response = self._request({"model": self.model, "prompt": text})
                    raw = response.get("embedding") if isinstance(response, dict) else None
                    result.append(_vector(raw, self.dimension))
        except EmbeddingError as exc:
            self._state, self._last_error = "unavailable", str(exc)
            raise
        self._state, self._last_error = "available", None
        return result

    def _request(self, payload: dict) -> dict:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > self.max_request_bytes:
            raise EmbeddingError("embedding request exceeds byte limit")
        request = Request(self.url, data=body, method="POST",
                          headers={"Content-Type": "application/json", "Accept": "application/json"})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
        except (HTTPError, URLError, OSError, TimeoutError) as exc:
            raise EmbeddingError(f"local Ollama embedding request failed: {exc}") from exc
        if len(raw) > self.max_response_bytes:
            raise EmbeddingError("Ollama embedding response exceeds byte limit")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmbeddingError("Ollama embedding response is not valid JSON") from exc
        if not isinstance(value, dict):
            raise EmbeddingError("Ollama embedding response must be an object")
        return value


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Bounded Gemini batch-embedding client authenticated with an API key."""

    def __init__(self, api_key, model: str, dimension: int, *, timeout: float = 15.0,
                 max_text_chars: int = 30000, max_batch_size: int = 32,
                 max_request_bytes: int = 1048576, max_response_bytes: int = 16777216,
                 opener=None) -> None:
        supplied_keys = [api_key] if isinstance(api_key, str) else list(api_key or ())
        if any(not isinstance(key, str) for key in supplied_keys):
            raise ValueError("Gemini API keys must be strings")
        supplied_keys = list(dict.fromkeys(key.strip() for key in supplied_keys if key.strip()))
        if not isinstance(model, str) or not model.strip() or len(model) > 200:
            raise ValueError("model must be a nonempty string of at most 200 characters")
        clean_model = model.strip().removeprefix("models/")
        if not clean_model or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-._" for character in clean_model):
            raise ValueError("model contains invalid characters")
        if type(dimension) is not int or not 128 <= dimension <= 3072:
            raise ValueError("Gemini embedding dimension must be between 128 and 3072")
        if not isinstance(timeout, (int, float)) or isinstance(timeout, bool) or not 0 < timeout <= 30:
            raise ValueError("timeout must be greater than 0 and at most 30 seconds")
        self._api_keys = tuple(supplied_keys)
        self._key_index = 0
        self.model = clean_model
        self.dimension = dimension
        self.timeout = float(timeout)
        self.max_text_chars = max_text_chars
        self.max_batch_size = max_batch_size
        self.max_request_bytes = max_request_bytes
        self.max_response_bytes = max_response_bytes
        self.url = ("https://generativelanguage.googleapis.com/v1beta/models/" +
                    self.model + ":batchEmbedContents")
        self._opener = opener if opener is not None else build_opener(ProxyHandler({}), _NoRedirect())
        self._state = "unknown" if self._api_keys else "unavailable"
        self._last_error = None if self._api_keys else "Gemini API key is unavailable"

    @property
    def identity(self) -> str:
        return f"gemini:{self.model}:{self.dimension}"

    def status(self) -> dict:
        return {"identity": self.identity, "state": self._state,
                "available": self._state == "available", "last_error": self._last_error,
                "semantic": True, "remote": True, "configured_keys": len(self._api_keys)}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list):
            raise EmbeddingError("texts must be a list")
        if not texts:
            return []
        if not self._api_keys:
            raise EmbeddingError("Gemini API key is unavailable")
        if len(texts) > self.max_batch_size:
            raise EmbeddingError(f"embedding batch exceeds {self.max_batch_size} texts")
        if any(not isinstance(text, str) or len(text) > self.max_text_chars for text in texts):
            raise EmbeddingError(f"each text must be a string of at most {self.max_text_chars} characters")
        model_name = "models/" + self.model
        payload = {"requests": [{"model": model_name,
                                  "content": {"parts": [{"text": text}]},
                                  "taskType": "SEMANTIC_SIMILARITY",
                                  "outputDimensionality": self.dimension}
                                 for text in texts]}
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > self.max_request_bytes:
            raise EmbeddingError("embedding request exceeds byte limit")
        try:
            raw = None
            last_error = None
            for attempt in range(len(self._api_keys)):
                index = (self._key_index + attempt) % len(self._api_keys)
                request = Request(self.url, data=body, method="POST",
                                  headers={"Content-Type": "application/json", "Accept": "application/json",
                                           "x-goog-api-key": self._api_keys[index]})
                try:
                    with self._opener.open(request, timeout=self.timeout) as response:
                        raw = response.read(self.max_response_bytes + 1)
                    self._key_index = index
                    break
                except (HTTPError, URLError, OSError, TimeoutError) as exc:
                    last_error = exc
            if raw is None:
                raise EmbeddingError(f"all configured Gemini API keys failed: {last_error}")
            if len(raw) > self.max_response_bytes:
                raise EmbeddingError("Gemini embedding response exceeds byte limit")
            value = json.loads(raw.decode("utf-8"))
            embeddings = value.get("embeddings") if isinstance(value, dict) else None
            if not isinstance(embeddings, list) or len(embeddings) != len(texts):
                raise EmbeddingError("Gemini response has the wrong embedding count")
            result = [_vector(item.get("values") if isinstance(item, dict) else None, self.dimension)
                      for item in embeddings]
        except (HTTPError, URLError, OSError, TimeoutError, UnicodeDecodeError,
                json.JSONDecodeError, EmbeddingError) as exc:
            self._state, self._last_error = "unavailable", str(exc)
            if isinstance(exc, EmbeddingError):
                raise
            raise EmbeddingError(f"Gemini embedding request failed: {exc}") from exc
        self._state, self._last_error = "available", None
        return result


class StaticEmbeddingProvider(EmbeddingProvider):
    """Deterministic test provider backed by explicit vectors; not semantic."""

    def __init__(self, vectors: Mapping[str, Sequence[float]], dimension: int) -> None:
        if type(dimension) is not int or dimension < 1:
            raise ValueError("dimension must be positive")
        self.dimension = dimension
        self._vectors = {text: _vector(list(vector), dimension) for text, vector in vectors.items()}

    @property
    def identity(self) -> str:
        return f"static-test:{self.dimension}"

    def status(self) -> dict:
        return {"identity": self.identity, "state": "available", "available": True,
                "last_error": None, "semantic": False}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise EmbeddingError("texts must be a list of strings")
        try:
            return [list(self._vectors[text]) for text in texts]
        except KeyError as exc:
            raise EmbeddingError(f"no static embedding for text: {exc.args[0]!r}") from exc


class DeterministicFakeEmbeddingProvider(EmbeddingProvider):
    """Hash-derived test vectors for arbitrary text; explicitly not semantic."""

    def __init__(self, dimension: int = 8) -> None:
        if type(dimension) is not int or not 1 <= dimension <= 1024:
            raise ValueError("dimension must be between 1 and 1024")
        self.dimension = dimension

    @property
    def identity(self) -> str:
        return f"deterministic-fake-test:{self.dimension}"

    def status(self) -> dict:
        return {"identity": self.identity, "state": "available", "available": True,
                "last_error": None, "semantic": False}

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not isinstance(texts, list) or any(not isinstance(text, str) for text in texts):
            raise EmbeddingError("texts must be a list of strings")
        result = []
        for text in texts:
            seed = sha256(text.encode("utf-8")).digest()
            result.append([(seed[index % len(seed)] - 127.5) / 127.5
                           for index in range(self.dimension)])
        return result


__all__ = ["EmbeddingError", "EmbeddingProvider", "OllamaEmbeddingProvider", "GeminiEmbeddingProvider",
           "StaticEmbeddingProvider", "DeterministicFakeEmbeddingProvider"]
