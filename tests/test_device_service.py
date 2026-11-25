from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DeviceCreate, StatusUpdate
from app.repositories.device_repository import InMemoryDeviceRepository
from app.services.device_service import DeviceAlreadyExistsError, DeviceNotFoundError, DeviceService


@pytest.fixture
def repository():
    return InMemoryDeviceRepository()


@pytest.fixture
def service(repository):
    return DeviceService(repository)


def test_registration(service):
    payload = DeviceCreate(name="router", device_type="router", ip_address="192.0.2.1")
    device = service.register(payload)
    assert service.get(device.device_id) == device
    assert service.list() == [device]


def test_duplicate_device_id(service):
    payload = DeviceCreate(name="router", device_type="router", ip_address="192.0.2.1")
    device = service.register(payload)
    with pytest.raises(DeviceAlreadyExistsError):
        service.register(payload)
    assert service.get(device.device_id) == device


def test_missing_device_id(service):
    with pytest.raises(DeviceNotFoundError):
        service.get(uuid4())
    with pytest.raises(DeviceNotFoundError):
        service.update_status(uuid4(), StatusUpdate(status="offline"))


def test_initial_offline_registration_has_no_alert(service):
    service.register(DeviceCreate(
        name="router", device_type="router", ip_address="192.0.2.1", status="offline"
    ))
    assert service.list_alerts() == []


def test_offline_transition_and_repeated_update(service):
    device = service.register(DeviceCreate(
        name="router", device_type="router", ip_address="192.0.2.1"
    ))
    service.update_status(device.device_id, StatusUpdate(status="offline"))
    alerts = service.list_alerts()
    assert len(alerts) == 1
    assert alerts[0].device_id == device.device_id
    service.update_status(device.device_id, StatusUpdate(status="offline"))
    assert service.list_alerts() == alerts


def test_alert_only_on_online_to_offline_transition(service, repository):
    with patch("app.services.device_service.create_offline_alert") as create_alert:
        device = service.register(DeviceCreate(
            name="router", device_type="router", ip_address="192.0.2.1", status="offline"
        ))
        service.update_status(device.device_id, StatusUpdate(status="offline"))
        create_alert.assert_not_called()
        service.update_status(device.device_id, StatusUpdate(status="online"))
        create_alert.assert_not_called()
        service.update_status(device.device_id, StatusUpdate(status="offline"))
        create_alert.assert_called_once_with(repository, device.device_id)
        service.update_status(device.device_id, StatusUpdate(status="offline"))
        create_alert.assert_called_once()
        service.update_status(device.device_id, StatusUpdate(status="online"))
        service.update_status(device.device_id, StatusUpdate(status="offline"))
        assert create_alert.call_count == 2


def test_offline_alerts_through_api(monkeypatch, service):
    monkeypatch.setattr("app.routes.devices.device_service", service)
    with TestClient(app) as client:
        offline = client.post("/devices", json={
            "name": "offline router", "device_type": "router",
            "ip_address": "192.0.2.1", "status": "offline",
        }).json()
        offline_path = f"/devices/{offline['device_id']}/status"
        assert client.patch(offline_path, json={"status": "offline"}).status_code == 200
        assert client.get("/alerts").json() == []

        device = client.post("/devices", json={
            "name": "online router", "device_type": "router", "ip_address": "192.0.2.2",
        }).json()
        status_path = f"/devices/{device['device_id']}/status"
        assert client.patch(status_path, json={"status": "offline"}).status_code == 200
        assert client.patch(status_path, json={"status": "offline"}).status_code == 200
        alerts = client.get("/alerts").json()
        assert len(alerts) == 1
        assert alerts[0]["device_id"] == device["device_id"]
        assert "went offline" in alerts[0]["message"]
        assert datetime.fromisoformat(alerts[0]["timestamp"]).utcoffset() == timezone.utc.utcoffset(None)