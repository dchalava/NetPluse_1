from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any
from uuid import UUID

from app.models import AlertResponse

if TYPE_CHECKING:
    from app.repositories.device_repository import InMemoryDeviceRepository


@dataclass(frozen=True)
class DeviceEvent:
    name: str
    device_id: str
    data: dict[str, Any]


EventHandler = Callable[[DeviceEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._handlers: list[EventHandler] = []

    def subscribe(self, handler: EventHandler) -> None:
        self._handlers.append(handler)

    def publish(self, event: DeviceEvent) -> None:
        for handler in self._handlers:
            handler(event)


event_bus = EventBus()


def create_offline_alert(repository: "InMemoryDeviceRepository", device_id: UUID) -> None:
    repository.save_alert(
        AlertResponse(
            device_id=device_id,
            message=f"Device {device_id} went offline",
            timestamp=datetime.now(timezone.utc),
        )
    )