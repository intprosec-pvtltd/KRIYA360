"""Tests that cover retried GPS sample ids, stale samples and manager fleet views."""
import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
os.environ['ADMIN_SETUP_KEY']='test-admin-migration-secret-with-32-characters'
from fastapi.testclient import TestClient
from app.main import app
from datetime import datetime,timezone,timedelta

client=TestClient(app)

def token(phone,pin):
    if phone=='9000000000':
        r=client.post('/api/auth/admin/login',json={'email':'manager@example.test','password':'TestStrongPassword12'})
        if r.status_code!=200:
            r=client.post('/api/auth/admin/setup',json={'phone':phone,'pin':pin,'email':'manager@example.test','password':'TestStrongPassword12','setup_key':os.environ['ADMIN_SETUP_KEY']})
    else:
        from app.main import SessionLocal,User,hash_pin
        with SessionLocal() as session:
            u=session.get(User,'driver-demo');u.pin_hash=hash_pin('1234');u.license_verified=True;u.approved=True;u.active=True;session.commit()
        r=client.post('/api/auth/login',json={'phone':phone,'pin':pin})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}

def test_gps_retry_does_not_duplicate_and_stale_point_does_not_move_marker():
    d=token('9000000001','1234')
    r=client.post('/api/attendance/punch-in',json={'lat':12.97,'lng':77.59},headers=d)
    assert r.status_code==200,r.text
    fresh=datetime.now(timezone.utc)+timedelta(seconds=1)
    sample={'lat':12.974,'lng':77.598,'accuracy_m':12,'captured_at':fresh.isoformat(),'sample_id':'live-test-unique-001'}
    a=client.post('/api/gps',json=sample,headers=d)
    assert a.status_code==200,a.text
    b=client.post('/api/gps',json=sample,headers=d)
    assert b.status_code==200 and b.json()['duplicate'] is True
    old={**sample,'sample_id':'live-test-unique-002','lat':13.11,'captured_at':(fresh-timedelta(seconds=1)).isoformat()}
    c=client.post('/api/gps',json=old,headers=d)
    assert c.status_code==200,c.text
    from app.main import SessionLocal,User,GPS
    from sqlalchemy import select,func
    with SessionLocal() as session:
        u=session.get(User,'driver-demo')
        assert u.lat==12.974
        n=session.scalar(select(func.count()).select_from(GPS).where(GPS.driver_id==u.id,GPS.sample_id=='live-test-unique-001'))
        assert n==1
    status=client.get('/api/tracking/status',headers=d)
    assert status.status_code==200 and status.json()['on_shift'] is True
    assert client.post('/api/attendance/punch-out',json={'lat':12.974,'lng':77.598},headers=d).status_code==200

def test_manager_fleet_view_and_role_restriction():
    m=token('9000000000','1234'); d=token('9000000001','1234')
    assert client.get('/api/tracking/fleet',headers=d).status_code==403
    response=client.get('/api/tracking/fleet',headers=m)
    assert response.status_code==200,response.text
    assert isinstance(response.json()['drivers'],list)
    for item in response.json()['drivers']:
        assert item['gps_status'] in ('no_gps','fresh','stale','offline')
        assert 'current_task' in item
