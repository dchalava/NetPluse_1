import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models import DeviceCreate, StatusUpdate
from app.repositories.device_repository import InMemoryDeviceRepository
from app.services.device_service import DeviceAlreadyExistsError, DeviceNotFoundError, DeviceService
from app.services.probe import simulate_device_probe


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


def test_empty_device_summary(service):
    assert service.get_device_summary().model_dump() == {
        "total_devices": 0, "online_count": 0, "offline_count": 0, "device_types": [],
    }


def test_device_summary(service):
    first = service.register(DeviceCreate(
        name="switch", device_type="switch", ip_address="192.0.2.1"
    ))
    service.register(DeviceCreate(
        name="router", device_type="router", ip_address="192.0.2.2", status="offline"
    ))
    service.register(DeviceCreate(
        name="other switch", device_type="switch", ip_address="192.0.2.3"
    ))
    service.register(DeviceCreate(
        name="server", device_type="server", ip_address="192.0.2.4", status="offline"
    ))
    assert service.get_device_summary().model_dump() == {
        "total_devices": 4, "online_count": 2, "offline_count": 2,
        "device_types": ["router", "server", "switch"],
    }
    service.update_status(first.device_id, StatusUpdate(status="offline"))
    assert service.get_device_summary().model_dump() == {
        "total_devices": 4, "online_count": 1, "offline_count": 3,
        "device_types": ["router", "server", "switch"],
    }


def test_device_summary_route(monkeypatch, service):
    monkeypatch.setattr("app.routes.devices.device_service", service)
    with TestClient(app) as client:
        assert client.get("/devices/summary").json() == {
            "total_devices": 0, "online_count": 0, "offline_count": 0, "device_types": [],
        }
        response = client.post("/devices", json={
            "name": "router", "device_type": "router", "ip_address": "192.0.2.1",
        })
        assert response.status_code == 201
        assert client.get("/devices/summary").json() == {
            "total_devices": 1, "online_count": 1, "offline_count": 0,
            "device_types": ["router"],
        }
        assert client.get(f"/devices/{response.json()['device_id']}").status_code == 200


def test_simulated_probe_waits_and_returns_reachable():
    with patch("app.services.probe.asyncio.sleep", new_callable=AsyncMock) as sleep:
        assert asyncio.run(simulate_device_probe("device-1")) == {
            "device_id": "device-1", "reachable": True, "simulated": True,
        }
        sleep.assert_awaited_once_with(0.2)


def test_probe_route_does_not_change_device_or_alerts(monkeypatch, service):
    monkeypatch.setattr("app.routes.devices.device_service", service)
    device = service.register(DeviceCreate(
        name="router", device_type="router", ip_address="192.0.2.1", status="offline"
    ))
    with TestClient(app) as client:
        response = client.get(f"/devices/{device.device_id}/probe")
        assert response.status_code == 200
        assert response.json() == {
            "device_id": str(device.device_id), "reachable": True, "simulated": True,
        }
        assert service.get(device.device_id) == device
        assert service.list_alerts() == []
        missing_id = uuid4()
        with patch("app.routes.devices.simulate_device_probe", new_callable=AsyncMock) as probe:
            missing = client.get(f"/devices/{missing_id}/probe")
            assert missing.status_code == 404
            assert missing.json() == {"detail": f"Device {missing_id} not found"}
            probe.assert_not_awaited()


def test_duplicate_device_id(service):
    payload = DeviceCreate(name="router", device_type="router", ip_address="192.0.2.1")
    device = service.register(payload)
    duplicate = DeviceCreate(
        device_id=device.device_id, name="other", device_type="server", ip_address="192.0.2.2"
    )
    with pytest.raises(DeviceAlreadyExistsError):
        service.register(duplicate)
    assert service.get(device.device_id) == device
    assert service.list() == [device]


def test_missing_device_id(service):
    with pytest.raises(DeviceNotFoundError):
        service.get(uuid4())
    with pytest.raises(DeviceNotFoundError):
        service.update_status(uuid4(), StatusUpdate(status="offline"))
    with pytest.raises(DeviceNotFoundError):
        service.delete_device(uuid4())


def test_domain_errors_and_validation_through_api(monkeypatch, service):
    monkeypatch.setattr("app.routes.devices.device_service", service)
    device_id = str(uuid4())
    payload = {
        "device_id": device_id, "name": "router", "device_type": "router",
        "ip_address": "192.0.2.1",
    }
    with TestClient(app) as client:
        assert client.post("/devices", json=payload).status_code == 201
        duplicate = client.post("/devices", json=payload)
        assert duplicate.status_code == 409
        assert duplicate.json() == {"detail": f"Device {device_id} already exists"}

        missing_id = str(uuid4())
        for response in (
            client.get(f"/devices/{missing_id}"),
            client.patch(f"/devices/{missing_id}/status", json={"status": "offline"}),
        ):
            assert response.status_code == 404
            assert response.json() == {"detail": f"Device {missing_id} not found"}

        assert client.get("/devices/not-a-uuid").status_code == 422
        assert client.patch(f"/devices/{device_id}/status", json={"status": "invalid"}).status_code == 422
        assert client.post("/devices", json={**payload, "ip_address": "not-an-ip"}).status_code == 422


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