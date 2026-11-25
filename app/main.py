from fastapi import APIRouter, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.routes.devices import alerts_router, router as devices_router
from app.services.device_service import DeviceAlreadyExistsError, DeviceNotFoundError


app = FastAPI(title="NetPulse API", version="0.1.0")


@app.exception_handler(DeviceAlreadyExistsError)
def device_already_exists_handler(_request: Request, error: DeviceAlreadyExistsError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_409_CONFLICT, content={"detail": str(error)})


@app.exception_handler(DeviceNotFoundError)
def device_not_found_handler(_request: Request, error: DeviceNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"detail": str(error)})


app.include_router(devices_router)
app.include_router(alerts_router)
health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=dict[str, str])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(health_router)