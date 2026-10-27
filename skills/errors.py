"""Shared exception type without importing the registry facade."""


class SkillError(ValueError):
    """A safe, user-presentable skill failure."""
