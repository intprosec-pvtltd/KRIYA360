"""Isolated by test_api's sqlite:// fixture; never contacts production."""
import uuid
from datetime import datetime,timedelta,timezone
from fastapi.testclient import TestClient
from app.main import app, SessionLocal, User
from test_api import auth
c=TestClient(app)

def example(ref):
 return {'order_reference':ref,'title':'Sample delivery','pickup_address':'Indiranagar, Bengaluru','pickup_lat':12.9784,'pickup_lng':77.6408,'delivery_address':'Whitefield, Bengaluru','delivery_lat':12.9698,'delivery_lng':77.75,'customer_name':'Sample customer','customer_phone':'9876543210','due_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'priority':'normal','vehicle_type':'','instructions':'Demo test'}

def test_preview_import_and_manager_confirmed_assignment():
 m=auth('9000000000');ref='TEST-'+uuid.uuid4().hex[:12].upper();body={'orders':[example(ref)]}
 before=len(c.get('/api/tasks',headers=m).json())
 p=c.post('/api/orders/bulk-preview',json=body,headers=m)
 assert p.status_code==200,p.text
 assert p.json()['valid']==1
 created=c.post('/api/orders/bulk-import',json=body,headers=m)
 assert created.status_code==201,created.text
 assert created.json()['assigned']==0
 assert len(c.get('/api/tasks',headers=m).json())==before
 order_id=created.json()['order_ids'][0]
 rec=c.get(f'/api/orders/{order_id}/recommendations',headers=m)
 assert rec.status_code==200,rec.text
 assert rec.json()['traffic_aware'] is False
 assert rec.json()['recommendations']
 d=rec.json()['recommendations'][0]['driver_id']
 result=c.post(f'/api/orders/{order_id}/assign',json={'driver_id':d},headers=m)
 assert result.status_code==201,result.text
 assert result.json()['task']['status']=='assigned'
 assert len(c.get('/api/tasks',headers=m).json())==before+1
 assert c.post(f'/api/orders/{order_id}/assign',json={'driver_id':d},headers=m).status_code==409
 assert c.post('/api/orders/bulk-import',json=body,headers=m).status_code==422

def test_invalid_csv_payload_atomic():
 m=auth('9000000000');ref='TEST-'+uuid.uuid4().hex[:12].upper();bad=example(ref);bad['pickup_lat']=101
 body={'orders':[example('TEST-'+uuid.uuid4().hex[:12].upper()),bad]}
 preview=c.post('/api/orders/bulk-preview',json=body,headers=m)
 assert preview.status_code==200 and preview.json()['invalid']==1
 before=len(c.get('/api/orders',headers=m).json())
 assert c.post('/api/orders/bulk-import',json=body,headers=m).status_code==422
 assert len(c.get('/api/orders',headers=m).json())==before

def test_duplicate_csv_rows_and_driver_security():
 m=auth('9000000000');d=auth('9000000001');ref='TEST-'+uuid.uuid4().hex[:12].upper()
 body={'orders':[example(ref),example(ref)]}
 p=c.post('/api/orders/bulk-preview',json=body,headers=m)
 assert p.status_code==200 and p.json()['invalid']==1
 assert 'Duplicate' in str(p.json()['rows'][1]['errors'])
 assert c.get('/api/orders',headers=d).status_code==403
 assert c.post('/api/orders/bulk-import',json=body,headers=d).status_code==403
