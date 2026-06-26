from typing import Any, Callable, Dict, List


class EventBus:
    def __init__(self) -> None:
        self.subscribers: Dict[str, List[Callable[[Any], None]]] = {}
        self.connected = False

    def connect(self) -> None:
        self.connected = True
        print("EventBus connected")

    def disconnect(self) -> None:
        self.connected = False
        print("EventBus disconnected")

    def subscribe(self, event_name: str, handler: Callable[[Any], None]) -> None:
        handlers = self.subscribers.setdefault(event_name, [])
        if handler not in handlers:
            handlers.append(handler)

    def publish(self, event_name: str, payload: Any) -> None:
        for handler in self.subscribers.get(event_name, []):
            handler(payload)


event_bus = EventBus()
