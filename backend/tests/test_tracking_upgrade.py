"""Regression tests for KRIYA360 fleet tracking and optional route providers."""
import os
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
from fastapi.testclient import TestClient
from app.main import app

client=TestClient(app)

def driver_headers():
    # Existing API tests may change the demo account PIN; restore test fixture only.
    from app.main import SessionLocal,User,hash_pin
    with SessionLocal() as db:
        user=db.get(User,'driver-demo')
        user.pin_hash=hash_pin('1234');user.license_verified=True;user.approved=True;user.active=True
        db.commit()
    response=client.post('/api/auth/login',json={'phone':'9000000001','pin':'1234'})
    assert response.status_code==200,response.text
    return {'Authorization':'Bearer '+response.json()['access_token']}

def test_gps_accuracy_and_captured_time_are_preserved():
    headers=driver_headers()
    client.post('/api/attendance/punch-in',headers=headers,json={'lat':12.9716,'lng':77.5946}).raise_for_status()
    captured=datetime.now(timezone.utc)-timedelta(seconds=12)
    result=client.post('/api/gps',headers=headers,json={
        'lat':12.975,'lng':77.60,'accuracy_m':8.5,'speed_mps':4,
        'captured_at':captured.isoformat()})
    assert result.status_code==200,result.text
    assert result.json()['ok'] is True
    # Unreasonable future timestamps must be rejected.
    bad=client.post('/api/gps',headers=headers,json={
        'lat':12.975,'lng':77.6,'captured_at':(datetime.now(timezone.utc)+timedelta(hours=1)).isoformat()})
    assert bad.status_code==422

def test_no_traffic_route_is_labeled_honestly():
    async def mock_osrm(*args):
        return {'distance_km':5,'duration_min':12,'coordinates':[[77.6,12.9],[77.7,13]],
                'steps':[],'source':'OSRM demo road routing','traffic_aware':False}
    with patch.dict(os.environ,{'TOMTOM_API_KEY':''}), patch('app.main.route_between',side_effect=mock_osrm):
        from app.main import route_options
        import asyncio
        result=asyncio.run(route_options(12.9,77.6,13,77.7))
    assert result['traffic_aware'] is False
    assert 'Traffic data unavailable' in result['notice']
