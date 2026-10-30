"""Minimal messages accepted by the parent-supplied generation engine."""

from dataclasses import dataclass
from enum import Enum


class Role(str, Enum):
    USER = "user"
    SYSTEM = "system"


@dataclass(slots=True)
class Message:
    role: Role
    content: str


__all__ = ["Message", "Role"]
