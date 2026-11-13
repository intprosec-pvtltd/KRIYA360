"""Reverse-location API validation; never connects to a live third-party service."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def manager_headers():
    result=client.post('/api/auth/admin/login',json={'email':'manager@example.test','password':'TestStrongPassword12'})
    assert result.status_code == 200, result.text
    return {'Authorization':'Bearer '+result.json()['access_token']}

def test_reverse_location_requires_authentication():
    assert client.get('/api/geocode/reverse?lat=13.0&lng=77.6').status_code == 401

def test_reverse_location_rejects_invalid_coordinates():
    assert client.get('/api/geocode/reverse?lat=200&lng=77.6',headers=manager_headers()).status_code == 422
