from datetime import datetime, timezone
from ipaddress import IPv4Address
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class DeviceCreate(BaseModel):
    model_config = ConfigDict(json_schema_extra={
        "examples": [{
            "name": "Core router",
            "device_type": "router",
            "ip_address": "192.0.2.1",
            "status": "online",
        }]
    })

    device_id: UUID = Field(default_factory=uuid4)
    name: str = Field(min_length=1, max_length=100)
    device_type: Literal["router", "switch", "server"]
    ip_address: IPv4Address
    status: Literal["online", "offline"] = "online"


class DeviceResponse(BaseModel):
    device_id: UUID = Field(default_factory=uuid4)
    name: str
    device_type: Literal["router", "switch", "server"]
    ip_address: IPv4Address
    status: Literal["online", "offline"] = "online"


class StatusUpdate(BaseModel):
    model_config = ConfigDict(json_schema_extra={"examples": [{"status": "offline"}]})

    status: Literal["online", "offline"]


class AlertResponse(BaseModel):
    device_id: UUID
    message: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))