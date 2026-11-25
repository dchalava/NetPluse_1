from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from app.main import app
from app.models import AlertResponse, DeviceResponse
from app.repositories.device_repository import InMemoryDeviceRepository
from app.services.device_service import device_service


def test_repository_copies_devices_and_alerts():
    repository = InMemoryDeviceRepository()
    device = DeviceResponse(name="router", device_type="router", ip_address="192.0.2.1")
    added = repository.add_device(device)
    device.name = "changed original"
    added.name = "changed result"
    listed = repository.list_devices()
    listed[0].name = "changed list"
    fetched = repository.get_device(device.device_id)
    assert fetched is not None
    assert fetched.name == "router"
    fetched.name = "changed fetch"
    updated = repository.update_status(device.device_id, "offline")
    assert updated is not None
    updated.status = "online"
    assert repository.get_device(device.device_id).status == "offline"
    assert repository.update_status(uuid4(), "online") is None

    alert = AlertResponse(device_id=device.device_id, message="offline")
    saved = repository.save_alert(alert)
    alert.message = "changed original"
    saved.message = "changed result"
    listed_alerts = repository.list_alerts()
    listed_alerts[0].message = "changed list"
    listed_alerts.clear()
    assert repository.list_alerts()[0].message == "offline"
    assert InMemoryDeviceRepository().list_devices() == []
    assert InMemoryDeviceRepository().list_alerts() == []


def test_devices_survive_across_requests():
    with TestClient(app) as client:
        response = client.post(
            "/devices",
            json={"name": "router", "device_type": "router", "ip_address": "192.0.2.1"},
        )
        assert response.status_code == 201
        device_id = response.json()["device_id"]
        duplicate = client.post(
            "/devices",
            json={"device_id": device_id, "name": "other", "device_type": "switch", "ip_address": "192.0.2.2"},
        )
        assert duplicate.status_code == 409
        assert client.get(f"/devices/{device_id}").json()["name"] == "router"
        assert client.patch(f"/devices/{device_id}/status", json={"status": "offline"}).json()["status"] == "offline"
        assert client.get(f"/devices/{device_id}").json()["status"] == "offline"
        device_service.delete_device(UUID(device_id))
        assert client.get(f"/devices/{device_id}").status_code == 404


def test_health_and_openapi_routes():
    with TestClient(app) as client:
        assert client.get("/health").json() == {"status": "ok"}
        schema = client.get("/openapi.json").json()
        paths = schema["paths"]
        assert {(method, path) for path, methods in paths.items() for method in methods} == {
            ("post", "/devices"),
            ("get", "/devices"),
            ("get", "/devices/{device_id}"),
            ("patch", "/devices/{device_id}/status"),
            ("get", "/alerts"),
            ("get", "/health"),
        }
        assert {"201", "409"} <= paths["/devices"]["post"]["responses"].keys()
        assert {"200", "404"} <= paths["/devices/{device_id}"]["get"]["responses"].keys()
        assert {"200", "404"} <= paths["/devices/{device_id}/status"]["patch"]["responses"].keys()
        models = schema["components"]["schemas"]
        device_example = models["DeviceCreate"]["examples"][0]
        assert set(device_example) == {"name", "device_type", "ip_address", "status"}
        assert models["StatusUpdate"]["examples"] == [{"status": "offline"}]