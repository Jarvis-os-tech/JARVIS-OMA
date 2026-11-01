"""Execution backend capability contracts.

The orchestration core owns task state and policy; execution backends only
describe and launch a task on a particular surface.  Keeping this contract
small lets the Munder-Difflin bridge consume JARVIS jobs without coupling it
to the current tmux implementation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class BackendCapabilities:
    """Stable, serializable description of an execution surface."""

    name: str
    surface: str
    visible: bool
    background: bool
    supports_parallel: bool = True
    supports_cancel: bool = True
    supports_pause: bool = False
    supports_steer: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "surface": self.surface,
            "visible": self.visible,
            "background": self.background,
            "supports_parallel": self.supports_parallel,
            "supports_cancel": self.supports_cancel,
            "supports_pause": self.supports_pause,
            "supports_steer": self.supports_steer,
        }


class ExecutionBackend(Protocol):
    """Minimal boundary exposed to a coordinator or external office UI."""

    @property
    def capabilities(self) -> BackendCapabilities:
        ...

    def describe(self) -> Mapping[str, object]:
        ...


class ProcessExecutionBackend:
    """Descriptor for JARVIS's supervised subprocess runner."""

    capabilities = BackendCapabilities(
        name="process",
        surface="process",
        visible=False,
        background=True,
        supports_parallel=True,
        supports_cancel=True,
    )

    def describe(self) -> Mapping[str, object]:
        return self.capabilities.as_dict()


class TmuxExecutionBackend:
    """Descriptor for the user-visible tmux runner.

    The existing ``DesktopAgentOrchestrator`` remains the implementation;
    this object is intentionally descriptive until the Munder bridge is added.
    """

    capabilities = BackendCapabilities(
        name="tmux",
        surface="terminal",
        visible=True,
        background=True,
        supports_parallel=True,
        supports_cancel=True,
        supports_pause=True,
        supports_steer=True,
    )

    def describe(self) -> Mapping[str, object]:
        return self.capabilities.as_dict()


def available_backends(*, tmux: bool) -> list[dict[str, object]]:
    """Return capability records for surfaces currently usable by JARVIS."""
    backends = [ProcessExecutionBackend().describe()]
    if tmux:
        backends.append(TmuxExecutionBackend().describe())
    return backends
