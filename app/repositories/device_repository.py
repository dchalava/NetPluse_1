from threading import RLock
from typing import Literal
from uuid import UUID

from app.models import AlertResponse, DeviceResponse


class InMemoryDeviceRepository:
    def __init__(self) -> None:
        self._devices: dict[UUID, DeviceResponse] = {}
        self._alerts: list[AlertResponse] = []
        self._lock = RLock()

    def add_device(self, device: DeviceResponse) -> DeviceResponse | None:
        with self._lock:
            if device.device_id in self._devices:
                return None
            self._devices[device.device_id] = device.model_copy(deep=True)
            return self._devices[device.device_id].model_copy(deep=True)

    def list_devices(self) -> list[DeviceResponse]:
        with self._lock:
            return [device.model_copy(deep=True) for device in self._devices.values()]

    def get_device(self, device_id: UUID) -> DeviceResponse | None:
        with self._lock:
            device = self._devices.get(device_id)
            return device.model_copy(deep=True) if device is not None else None

    def update_status(
        self, device_id: UUID, status: Literal["online", "offline"]
    ) -> DeviceResponse | None:
        result = self.transition_status(device_id, status)
        return result[1] if result is not None else None

    def transition_status(
        self, device_id: UUID, status: Literal["online", "offline"]
    ) -> tuple[DeviceResponse, DeviceResponse] | None:
        with self._lock:
            device = self._devices.get(device_id)
            if device is None:
                return None
            updated = device.model_copy(update={"status": status}, deep=True)
            self._devices[device_id] = updated
            return device.model_copy(deep=True), updated.model_copy(deep=True)

    def save_alert(self, alert: AlertResponse) -> AlertResponse:
        with self._lock:
            self._alerts.append(alert.model_copy(deep=True))
            return self._alerts[-1].model_copy(deep=True)

    def list_alerts(self) -> list[AlertResponse]:
        with self._lock:
            return [alert.model_copy(deep=True) for alert in self._alerts]

    def delete_device(self, device_id: UUID) -> DeviceResponse | None:
        with self._lock:
            device = self._devices.pop(device_id, None)
            return device.model_copy(deep=True) if device is not None else None