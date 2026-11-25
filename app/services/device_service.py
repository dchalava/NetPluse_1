from __future__ import annotations

from uuid import UUID

from app.events import DeviceEvent, create_offline_alert, event_bus
from app.models import AlertResponse, DeviceCreate, DeviceResponse, DeviceSummaryResponse, StatusUpdate
from app.repositories.contracts import DeviceRepository
from app.repositories.device_repository import InMemoryDeviceRepository


class DeviceAlreadyExistsError(ValueError):
    pass


class DeviceNotFoundError(LookupError):
    pass


class DeviceService:
    def __init__(self, repository: DeviceRepository) -> None:
        self._repository = repository

    def register(self, payload: DeviceCreate) -> DeviceResponse:
        device = DeviceResponse(**payload.model_dump())
        created = self._repository.add_device(device)
        if created is None:
            raise DeviceAlreadyExistsError(f"Device {device.device_id} already exists")
        self._publish("device.created", created)
        return created

    def list(self) -> list[DeviceResponse]:
        return self._repository.list_devices()

    def get_device_summary(self) -> DeviceSummaryResponse:
        devices = self._repository.list_devices()
        counts = {"online": 0, "offline": 0}
        device_types = set()
        for device in devices:
            counts[device.status] += 1
            device_types.add(device.device_type)
        return DeviceSummaryResponse(
            total_devices=len(devices),
            online_count=counts["online"],
            offline_count=counts["offline"],
            device_types=sorted(device_types),
        )

    def list_alerts(self) -> list[AlertResponse]:
        return self._repository.list_alerts()

    def get(self, device_id: UUID) -> DeviceResponse:
        device = self._repository.get_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        return device

    def get_device(self, device_id: UUID) -> DeviceResponse:
        return self.get(device_id)

    def update_status(self, device_id: UUID, payload: StatusUpdate) -> DeviceResponse:
        transition = self._repository.transition_status(device_id, payload.status)
        if transition is None:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        previous, updated = transition
        if previous.status == "online" and updated.status == "offline":
            create_offline_alert(self._repository, device_id)
        self._publish("device.updated", updated)
        return updated

    def delete_device(self, device_id: UUID) -> None:
        device = self._repository.delete_device(device_id)
        if device is None:
            raise DeviceNotFoundError(f"Device {device_id} not found")
        self._publish("device.deleted", device)

    @staticmethod
    def _publish(event_name: str, device: DeviceResponse) -> None:
        event_bus.publish(
            DeviceEvent(
                name=event_name,
                device_id=str(device.device_id),
                data=device.model_dump(mode="json"),
            )
        )


device_service = DeviceService(InMemoryDeviceRepository())