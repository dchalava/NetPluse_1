from uuid import UUID

from fastapi import APIRouter, status

from app.models import AlertResponse, DeviceCreate, DeviceResponse, DeviceSummaryResponse, StatusUpdate
from app.services.device_service import device_service
from app.services.probe import simulate_device_probe


router = APIRouter(prefix="/devices", tags=["devices"])
alerts_router = APIRouter(tags=["alerts"])


@router.post(
    "", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Device ID already exists"}},
)
def create_device(payload: DeviceCreate) -> DeviceResponse:
    return device_service.register(payload)


@router.get("", response_model=list[DeviceResponse])
def list_devices() -> list[DeviceResponse]:
    return device_service.list()


@router.get("/summary", response_model=DeviceSummaryResponse)
def get_device_summary() -> DeviceSummaryResponse:
    return device_service.get_device_summary()


@router.get(
    "/{device_id}", response_model=DeviceResponse,
    responses={404: {"description": "Device not found"}},
)
def get_device(device_id: UUID) -> DeviceResponse:
    return device_service.get(device_id)


@router.get("/{device_id}/probe", responses={404: {"description": "Device not found"}})
async def probe_device(device_id: UUID) -> dict[str, str | bool]:
    device_service.get_device(device_id)
    return await simulate_device_probe(str(device_id))


@router.patch(
    "/{device_id}/status", response_model=DeviceResponse,
    responses={404: {"description": "Device not found"}},
)
def update_device(device_id: UUID, payload: StatusUpdate) -> DeviceResponse:
    return device_service.update_status(device_id, payload)


@alerts_router.get("/alerts", response_model=list[AlertResponse])
def list_alerts() -> list[AlertResponse]:
    return device_service.list_alerts()