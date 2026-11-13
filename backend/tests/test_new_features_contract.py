"""KRIYA360 approved role and bulk-delivery API contract tests.

Uses the pre-existing isolated in-memory SQLite fixture configured by test_api.py.
Never connects to production PostgreSQL.
"""
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, User

client = TestClient(app)

def token_for_phone(phone):
    pin='1234'
    if phone=='9000000000':
        r=client.post('/api/auth/admin/login',json={'email':'manager@example.test','password':'TestStrongPassword12'})
    else:
        r=client.post('/api/auth/login',json={'phone':phone,'pin':pin})
    assert r.status_code==200,r.text
    return {'Authorization':'Bearer '+r.json()['access_token']}

def test_bulk_deliveries_are_queued_not_started():
    manager=token_for_phone('9000000000')
    req={'deliveries':[{'title':'Bulk test task','driver_id':'driver-demo','address':'Sample location','lat':13.011,'lng':77.668,'due_at':(datetime.now(timezone.utc)+timedelta(days=1)).isoformat(),'customer_phone':'9876543210'}]}
    before=client.get('/api/tasks',headers=manager).json()
    preview=client.post('/api/tasks/bulk-preview',json=req,headers=manager)
    assert preview.status_code==200,preview.text
    assert preview.json()['valid']==1
    commit=client.post('/api/tasks/bulk-commit',json=req,headers=manager)
    assert commit.status_code==201,commit.text
    created=client.get('/api/tasks',headers=manager).json()
    assert len(created)==len(before)+1
    assert next(t for t in created if t['id']==commit.json()['task_ids'][0])['status']=='assigned'

def test_bulk_invalid_is_atomic():
    manager=token_for_phone('9000000000')
    due=(datetime.now(timezone.utc)+timedelta(days=1)).isoformat()
    req={'deliveries':[{'title':'Good','driver_id':'driver-demo','address':'Sample','lat':13.0,'lng':77.6,'due_at':due,'customer_phone':'9876543210'}, {'title':'Bad','driver_id':'missing-driver','address':'Sample','lat':13.0,'lng':77.6,'due_at':due,'customer_phone':'9876543210'}]}
    before=len(client.get('/api/tasks',headers=manager).json())
    assert client.post('/api/tasks/bulk-preview',json=req,headers=manager).json()['invalid']==1
    assert client.post('/api/tasks/bulk-commit',json=req,headers=manager).status_code==422
    assert len(client.get('/api/tasks',headers=manager).json())==before
