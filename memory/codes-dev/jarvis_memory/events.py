"""Optional event-bus contract for memory service integration."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Protocol


class EventType(str, Enum):
    CHAT_EXCHANGE_COMPLETED = "chat_exchange_completed"


@dataclass(slots=True)
class Event:
    event_type: EventType
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)


Subscriber = Callable[[Event], None]


class EventBus(Protocol):
    """Interface only; callers may supply a bus or use direct submission."""

    def subscribe(self, event_type: EventType, callback: Subscriber) -> None: ...

    def unsubscribe(self, event_type: EventType, callback: Subscriber) -> None: ...

    def publish(
        self, event_type: EventType, data: dict[str, Any] | None = None
    ) -> Event: ...


__all__ = ["Event", "EventBus", "EventType", "Subscriber"]
