from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.models import AlertResponse, DeviceCreate, DeviceResponse, StatusUpdate
from app.services.device_service import DeviceAlreadyExistsError, DeviceNotFoundError, device_service


router = APIRouter(prefix="/devices", tags=["devices"])
alerts_router = APIRouter(tags=["alerts"])


@router.post(
    "", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED,
    responses={409: {"description": "Device ID already exists"}},
)
def create_device(payload: DeviceCreate) -> DeviceResponse:
    try:
        return device_service.register(payload)
    except DeviceAlreadyExistsError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error


@router.get("", response_model=list[DeviceResponse])
def list_devices() -> list[DeviceResponse]:
    return device_service.list()


@router.get(
    "/{device_id}", response_model=DeviceResponse,
    responses={404: {"description": "Device not found"}},
)
def get_device(device_id: UUID) -> DeviceResponse:
    try:
        return device_service.get(device_id)
    except DeviceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@router.patch(
    "/{device_id}/status", response_model=DeviceResponse,
    responses={404: {"description": "Device not found"}},
)
def update_device(device_id: UUID, payload: StatusUpdate) -> DeviceResponse:
    try:
        return device_service.update_status(device_id, payload)
    except DeviceNotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@alerts_router.get("/alerts", response_model=list[AlertResponse])
def list_alerts() -> list[AlertResponse]:
    return device_service.list_alerts()