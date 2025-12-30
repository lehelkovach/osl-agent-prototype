import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional


@dataclass
class Event:
    """Simple event wrapper."""
    type: str
    payload: Dict[str, Any]


Listener = Callable[[Event], Awaitable[None]]


class EventBus:
    """
    Minimal async event bus. Listeners are async callables.
    """

    def __init__(self):
        self._listeners: Dict[str, List[Listener]] = {}

    def on(self, event_type: str, listener: Listener):
        self._listeners.setdefault(event_type, []).append(listener)

    async def emit(self, event_type: str, payload: Dict[str, Any]):
        listeners = self._listeners.get(event_type, []) + self._listeners.get("*", [])
        if not listeners:
            return
        event = Event(event_type, payload)
        # Run listeners concurrently
        await asyncio.gather(*(listener(event) for listener in listeners))


class NullEventBus(EventBus):
    """No-op bus for when events are not needed."""

    def on(self, event_type: str, listener: Listener):
        return

    async def emit(self, event_type: str, payload: Dict[str, Any]):
        return
