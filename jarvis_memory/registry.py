"""Minimal local registry for pluggable fact stores."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from .store import FactStore


class FactStoreRegistry:
    """Register and construct fact-store backends by name."""

    _entries: dict[str, type[FactStore]] = {}

    @classmethod
    def register(cls, key: str) -> Callable[[type[FactStore]], type[FactStore]]:
        def decorator(entry: type[FactStore]) -> type[FactStore]:
            return cls.register_value(key, entry)

        return decorator

    @classmethod
    def register_value(cls, key: str, value: type[FactStore]) -> type[FactStore]:
        if key in cls._entries:
            raise ValueError(f"{cls.__name__} already has an entry for '{key}'")
        cls._entries[key] = value
        return value

    @classmethod
    def get(cls, key: str) -> type[FactStore]:
        try:
            return cls._entries[key]
        except KeyError as exc:
            raise KeyError(f"{cls.__name__} does not have an entry for '{key}'") from exc

    @classmethod
    def create(cls, key: str, *args: Any, **kwargs: Any) -> FactStore:
        entry = cls.get(key)
        if not callable(entry):
            raise TypeError(
                f"{cls.__name__} entry '{key}' is not callable"
                " and cannot be instantiated"
            )
        return entry(*args, **kwargs)

    @classmethod
    def items(cls) -> tuple[tuple[str, type[FactStore]], ...]:
        return tuple(cls._entries.items())

    @classmethod
    def keys(cls) -> tuple[str, ...]:
        return tuple(cls._entries.keys())

    @classmethod
    def contains(cls, key: str) -> bool:
        return key in cls._entries

    @classmethod
    def clear(cls) -> None:
        cls._entries.clear()


__all__ = ["FactStoreRegistry"]
