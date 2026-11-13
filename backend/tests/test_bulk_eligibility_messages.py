"""Bulk preview should tell authorized managers why a driver is ineligible.
Uses the isolated test database installed by test_api; never production DB.
"""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_unknown_driver_has_actionable_error():
    login = client.post('/api/auth/admin/login', json={
        'email': 'manager@example.test', 'password': 'TestStrongPassword12'
    })
    assert login.status_code == 200
    auth = {'Authorization': 'Bearer ' + login.json()['access_token']}
    due = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    preview = client.post('/api/tasks/bulk-preview', headers=auth, json={'deliveries':[{
        'title':'Test assignment', 'driver_id':'REPLACE_WITH_ELIGIBLE_DRIVER_ID',
        'address':'Sample address', 'lat':13.01,'lng':77.67,
        'due_at':due,'customer_phone':'9876543210'
    }]})
    assert preview.status_code == 200, preview.text
    row = preview.json()['rows'][0]
    assert row['valid'] is False
    assert 'Driver ID not found' in row['errors'][0]
    assert 'placeholder' in row['errors'][0]
