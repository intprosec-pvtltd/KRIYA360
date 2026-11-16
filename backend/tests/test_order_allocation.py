"""Bulk-order allocation regression tests.

Uses the test_api SQLite test fixture. Never targets production PostgreSQL.
"""
import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.main import app, SessionLocal, Task
from test_api import auth

c = TestClient(app)

# Match the queue-state rules in app.main.delivery_queue_state().
OUTSTANDING_STATUSES = (
    "assigned",
    "in_progress",
    "queued",
    "ready_for_acceptance",
)


def example(ref):
    return {
        "order_reference": ref,
        "title": "Sample delivery",
        "pickup_address": "Indiranagar, Bengaluru",
        "pickup_lat": 12.9784,
        "pickup_lng": 77.6408,
        "delivery_address": "Whitefield, Bengaluru",
        "delivery_lat": 12.9698,
        "delivery_lng": 77.75,
        "customer_name": "Sample customer",
        "customer_phone": "9876543210",
        "due_at": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
        "priority": "normal",
        "vehicle_type": "",
        "instructions": "Demo test",
    }


def test_preview_import_and_manager_confirmed_assignment():
    manager_headers = auth("9000000000")
    reference = "TEST-" + uuid.uuid4().hex[:12].upper()
    body = {"orders": [example(reference)]}

    before = len(c.get("/api/tasks", headers=manager_headers).json())

    preview = c.post("/api/orders/bulk-preview", json=body, headers=manager_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["valid"] == 1

    created = c.post("/api/orders/bulk-import", json=body, headers=manager_headers)
    assert created.status_code == 201, created.text
    assert created.json()["assigned"] == 0
    assert len(c.get("/api/tasks", headers=manager_headers).json()) == before

    order_id = created.json()["order_ids"][0]
    recommendations = c.get(
        f"/api/orders/{order_id}/recommendations", headers=manager_headers
    )
    assert recommendations.status_code == 200, recommendations.text
    assert recommendations.json()["traffic_aware"] is False
    assert recommendations.json()["recommendations"]

    driver_id = recommendations.json()["recommendations"][0]["driver_id"]

    # Determine whether this driver already has outstanding work BEFORE assigning.
    # A free driver receives an assigned primary task; a busy driver gets a
    # queued secondary task. This is a stronger assertion than accepting either.
    with SessionLocal() as session:
        outstanding = session.scalar(
            select(Task.id)
            .where(
                Task.driver_id == driver_id,
                Task.status.in_(OUTSTANDING_STATUSES),
            )
            .limit(1)
        )
    expected_status = "queued" if outstanding is not None else "assigned"

    result = c.post(
        f"/api/orders/{order_id}/assign",
        json={"driver_id": driver_id},
        headers=manager_headers,
    )
    assert result.status_code == 201, result.text
    task = result.json()["task"]
    assert task["driver_id"] == driver_id
    assert task["status"] == expected_status, (
        f"Expected {expected_status!r} for driver {driver_id}, "
        f"got {task['status']!r}"
    )
    assert len(c.get("/api/tasks", headers=manager_headers).json()) == before + 1

    # No double assignment and no reimport of an existing order reference.
    assert c.post(
        f"/api/orders/{order_id}/assign",
        json={"driver_id": driver_id},
        headers=manager_headers,
    ).status_code == 409
    assert c.post(
        "/api/orders/bulk-import", json=body, headers=manager_headers
    ).status_code == 422


def test_invalid_csv_payload_atomic():
    manager_headers = auth("9000000000")
    reference = "TEST-" + uuid.uuid4().hex[:12].upper()
    invalid_order = example(reference)
    invalid_order["pickup_lat"] = 101
    body = {
        "orders": [
            example("TEST-" + uuid.uuid4().hex[:12].upper()),
            invalid_order,
        ]
    }

    preview = c.post(
        "/api/orders/bulk-preview", json=body, headers=manager_headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["invalid"] == 1

    before = len(c.get("/api/orders", headers=manager_headers).json())
    result = c.post(
        "/api/orders/bulk-import", json=body, headers=manager_headers
    )
    assert result.status_code == 422, result.text
    assert len(c.get("/api/orders", headers=manager_headers).json()) == before


def test_duplicate_csv_rows_and_driver_security():
    manager_headers = auth("9000000000")
    driver_headers = auth("9000000001")
    reference = "TEST-" + uuid.uuid4().hex[:12].upper()
    body = {"orders": [example(reference), example(reference)]}

    preview = c.post(
        "/api/orders/bulk-preview", json=body, headers=manager_headers
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["invalid"] == 1
    assert "Duplicate" in str(preview.json()["rows"][1]["errors"])

    assert c.get("/api/orders", headers=driver_headers).status_code == 403
    assert c.post(
        "/api/orders/bulk-import", json=body, headers=driver_headers
    ).status_code == 403
