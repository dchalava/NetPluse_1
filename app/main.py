from fastapi import APIRouter, FastAPI

from app.routes.devices import alerts_router, router as devices_router


app = FastAPI(title="NetPulse API", version="0.1.0")
app.include_router(devices_router)
app.include_router(alerts_router)
health_router = APIRouter(tags=["health"])


@health_router.get("/health", response_model=dict[str, str])
def health_check() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(health_router)