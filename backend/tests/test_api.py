import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
os.environ['ADMIN_SETUP_KEY']='test-admin-migration-secret-with-32-characters'
from fastapi.testclient import TestClient
from app.main import app
c=TestClient(app)
def auth(phone):
 if phone=='9000000000':
  r=c.post('/api/auth/admin/login',json={'email':'manager@example.test','password':'TestStrongPassword12'})
  if r.status_code!=200:
   r=c.post('/api/auth/admin/setup',json={'phone':phone,'pin':'1234','email':'manager@example.test','password':'TestStrongPassword12','setup_key':os.environ['ADMIN_SETUP_KEY']})
 else:r=c.post('/api/auth/login',json={'phone':phone,'pin':'1234'})
 assert r.status_code==200,r.text
 return {'Authorization':'Bearer '+r.json()['access_token']}
def test_health():assert c.get('/api/health').json()['ok']
def test_role_and_workflow():
 m=auth('9000000000');d=auth('9000000001')
 assert c.get('/api/drivers',headers=d).status_code==403
 assert c.get('/api/drivers',headers=m).status_code==200
 r=c.post('/api/attendance/punch-in',json={'lat':12.9716,'lng':77.5946,'vehicle':'Bike'},headers=d);assert r.status_code==200,r.text
 r=c.post('/api/gps',json={'lat':12.98,'lng':77.6},headers=d);assert r.status_code==200,r.text
 r=c.post('/api/sos',json={'confirmed':False},headers=d);assert r.status_code==400
 r=c.post('/api/sos',json={'confirmed':True,'lat':12.98,'lng':77.6},headers=d);assert r.status_code==200,r.text
 assert any(a['kind']=='sos' for a in c.get('/api/alerts',headers=m).json())
 r=c.post('/api/attendance/punch-out',json={'lat':12.98,'lng':77.6},headers=d);assert r.status_code==200,r.text

def test_delivery_expense_proof():
 from unittest.mock import patch
 from datetime import datetime,timedelta,timezone
 from io import BytesIO
 from PIL import Image
 m=auth('9000000000');d=auth('9000000001')
 from app.main import SessionLocal,User
 with SessionLocal() as s:
  u=s.get(User,'driver-demo');u.shift_start=None;u.shift_end=None;u.license_verified=True;s.commit() # temporary fixture only
 assert c.post('/api/attendance/punch-in',json={'lat':12.9716,'lng':77.5946},headers=d).status_code==200
 body={'title':'Demo package','driver_id':'driver-demo','address':'Whitefield Bengaluru','lat':12.9698,'lng':77.7500,'due_at':(datetime.now(timezone.utc)+timedelta(hours=4)).isoformat(),'customer':'Demo recipient','customer_phone':'9876543210'}
 with patch('app.main.route_between',return_value={'distance_km':8,'duration_min':30,'coordinates':[[77.5946,12.9716],[77.75,12.9698]],'source':'OSRM demo road routing'}):
  r=c.post('/api/tasks',json=body,headers=m)
 assert r.status_code==200,r.text;tid=r.json()['id']
 assert c.post(f'/api/tasks/{tid}/start',headers=d).status_code==200
 assert c.post(f'/api/tasks/{tid}/otp/generate',headers=m).status_code==410
 assert c.post(f'/api/tasks/{tid}/otp/send',headers=m).status_code==403
 assert c.post(f'/api/tasks/{tid}/otp/send',headers=d).status_code==503  # no SMS secrets
 from unittest.mock import AsyncMock,MagicMock
 response=MagicMock();response.json.return_value={'sid':'SM_TEST'};response.raise_for_status.return_value=None
 client=MagicMock();client.post=AsyncMock(return_value=response)
 client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=None)
 with patch.dict('os.environ',{'TWILIO_ACCOUNT_SID':'AC_TEST','TWILIO_AUTH_TOKEN':'test-secret','TWILIO_FROM_NUMBER':'+15550000000'}),patch('app.main.httpx.AsyncClient',return_value=client),patch('app.main.secrets.randbelow',return_value=123456):
  sent=c.post(f'/api/tasks/{tid}/otp/send',headers=d)
 assert sent.status_code==200,sent.text
 assert sent.json()['status']=='accepted_by_sms_provider' and 'otp' not in sent.json()
 assert '+919876543210'==client.post.call_args.kwargs['data']['To']
 code='123456'
 im=Image.new('RGB',(50,50),'red');b=BytesIO();im.save(b,'PNG');b.seek(0)
 assert c.post(f'/api/tasks/{tid}/complete',data={'otp':'000000'},files={'image':('x.png',b,'image/png')},headers=d).status_code==400
 b.seek(0)
 result=c.post(f'/api/tasks/{tid}/complete',data={'otp':code},files={'image':('x.png',b,'image/png')},headers=d)
 assert result.status_code==200,result.text
 assert result.json()['otp_verified']
 assert c.get(result.json()['proof_url'],headers=d).status_code==200
 expense=c.post('/api/expenses/submit-evidence',data={'task_id':tid,'amount':'150','category':'fuel'},files={'image':('receipt.png',b.getvalue(),'image/png')},headers=d)
 assert expense.status_code==200,expense.text
 assert c.patch('/api/expenses/'+expense.json()['id'],json={'status':'approved'},headers=m).status_code==409
 assert c.get(expense.json()['receipt_url'],headers=m).status_code==200
 assert c.post('/api/expenses/'+expense.json()['id']+'/mark-reviewed',headers=m).status_code==200
 assert c.patch('/api/expenses/'+expense.json()['id'],json={'status':'approved'},headers=m).status_code==200
 assert c.get('/api/overview',headers=m).json()['approved_expenses']>=150
 assert c.post('/api/attendance/punch-out',json={'lat':12.9716,'lng':77.5946},headers=d).status_code==200


def test_manager_onboarding_review_crud_and_late_reason():
 from io import BytesIO
 from PIL import Image
 from unittest.mock import patch
 from datetime import datetime,timedelta,timezone
 m=auth('9000000000')
 data={'name':'New Test Driver','phone':'9000011002','pin':'4422','license_no':'KA0120230001234','vehicle':'Lorry','shift_expected':'09:30'}
 assert c.post('/api/auth/register-driver',json=data).status_code==403
 bad={**data,'license_no':'DL-TEST-01','phone':'9000011003'}
 assert c.post('/api/drivers',json=bad,headers=m).status_code==422
 r=c.post('/api/drivers',json=data,headers=m);assert r.status_code==200,r.text
 uid=r.json()['id'];assert not r.json()['approved'];assert not r.json()['license_verified']
 pending=c.post('/api/auth/login',json={'phone':data['phone'],'pin':data['pin']});assert pending.status_code==200
 assert pending.json()['enrollment_only'] is True
 h={'Authorization':'Bearer '+pending.json()['access_token']}
 assert c.get('/api/driver/notifications',headers=h).status_code==403
 im=Image.new('RGB',(64,64),'blue');b=BytesIO();im.save(b,'PNG');raw=b.getvalue()
 assert c.post('/api/onboarding/license',files={'image':('license.png',raw,'image/png')},headers=h).status_code==200
 assert c.post('/api/onboarding/face',files={'image':('face.png',raw,'image/png')},headers=h).status_code==400
 assert c.post('/api/onboarding/license',files={'image':('license.png',raw,'image/png')},headers=h).status_code==409
 assert c.get('/api/onboarding/status',headers=h).json()['license_status']=='pending'
 rejected=c.patch(f'/api/drivers/{uid}/approval',json={'approved':False,'review_note':'Incorrect document number'},headers=m)
 assert rejected.status_code==200 and rejected.json()['license_status']=='rejected'
 assert c.get('/api/driver/notifications',headers=h).status_code==403
 assert c.post('/api/onboarding/license',files={'image':('corrected-license.png',raw,'image/png')},headers=h).status_code==200
 assert c.get('/api/onboarding/status',headers=h).json()['license_status']=='pending'
 assert c.patch(f'/api/drivers/{uid}/approval',json={'approved':True},headers=m).status_code==409
 assert c.patch(f'/api/drivers/{uid}/approval',json={'approved':True,'license_matches':True},headers=m).status_code==409
 licence_url=c.get('/api/drivers',headers=m).json()[-1]['license_url']
 assert c.get(licence_url,headers=m).status_code==200
 assert c.patch(f'/api/drivers/{uid}/approval',json={'approved':True,'license_matches':True},headers=m).status_code==200
 d=c.post('/api/auth/login',json={'phone':data['phone'],'pin':data['pin']});assert d.status_code==200 and not d.json().get('enrollment_only')
 dh={'Authorization':'Bearer '+d.json()['access_token']}
 assert c.get('/api/driver/notifications',headers=dh).status_code==200
 edited={**data,'phone':'9000011004','active':True}
 resp=c.patch(f'/api/drivers/{uid}',json=edited,headers=m)
 assert resp.status_code==200 and resp.json()['phone']=='9000011004'
 assert c.post('/api/auth/login',json={'phone':'9000011004','pin':'4422'}).status_code==200
 due=(datetime.now(timezone.utc)+timedelta(hours=2)).isoformat()
 body={'title':'Demo delivery','driver_id':uid,'address':'Warehouse B','lat':12.9,'lng':77.7,'due_at':due,'customer_phone':'9876543210'}
 with patch('app.main.route_between',return_value={'distance_km':8,'duration_min':30,'coordinates':[[77.6,12.9],[77.7,12.9]],'source':'mock routing'}):
  task=c.post('/api/tasks',json=body,headers=m)
 assert task.status_code==200,task.text;tid=task.json()['id']
 reported=c.post(f'/api/tasks/{tid}/late-reason',json={'reason':'Road closure ahead of truck'},headers=dh)
 assert reported.status_code==200 and 'Road closure' in reported.json()['late_reason']
 assert any(a['kind']=='driver_delay_reason' for a in c.get('/api/alerts',headers=m).json())
 assert c.delete(f'/api/drivers/{uid}',headers=m).status_code==409 # active task protects audit records
 updated={**edited,'license_no':'KA0120230005678'}
 changed=c.patch(f'/api/drivers/{uid}',json=updated,headers=m)
 assert changed.status_code==200 and not changed.json()['license_verified']
 with patch('app.main.route_between',return_value={'distance_km':8,'duration_min':30,'coordinates':[[77.6,12.9],[77.7,12.9]],'source':'mock routing'}):
  assert c.post('/api/tasks',json=body,headers=m).status_code==409

def test_management_crud_and_geocode():
 from unittest.mock import patch,AsyncMock,MagicMock
 m=auth('9000000000'); d=auth('9000000001')
 assert c.get('/api/management/users',headers=d).status_code==403
 assert c.post('/api/management/users',headers=d,json={'name':'Unauthorized','phone':'9876543210','pin':'4321'}).status_code==403
 r=c.post('/api/management/users',headers=m,json={'name':'Second Manager','phone':'9876543210','email':'second@example.test','password':'SecondManagerStrong12'})
 assert r.status_code==200,r.text
 uid=r.json()['id']
 assert c.patch('/api/management/users/'+uid,headers=m,json={'name':'New Manager','phone':'9876543210'}).status_code==200
 assert c.delete('/api/management/users/manager-demo',headers=m).status_code==409
 assert c.delete('/api/management/users/'+uid,headers=m).status_code==200
 assert c.post('/api/auth/admin/login',json={'email':'second@example.test','password':'SecondManagerStrong12'}).status_code==403
 assert c.get('/api/geocode/search?q=ab',headers=m).status_code==422
 response=MagicMock();response.json.return_value=[{'display_name':'Whitefield Bengaluru','lat':'12.97','lon':'77.75'}]
 response.raise_for_status.return_value=None
 client=MagicMock();client.get=AsyncMock(return_value=response)
 client.__aenter__=AsyncMock(return_value=client);client.__aexit__=AsyncMock(return_value=None)
 with patch('app.main.httpx.AsyncClient',return_value=client):
  r=c.get('/api/geocode/search?q=Whitefield%20Bengaluru',headers=m)
 assert r.status_code==200,r.text
 assert len(r.json()['results'])==1

def test_attendance_report_and_csv_download():
 m=auth('9000000000')
 r=c.get('/api/reports/attendance',headers=m)
 assert r.status_code==200,r.text
 assert 'records' in r.json() and 'drivers' in r.json()
 assert c.get('/api/reports/attendance.csv',headers=m).status_code==200
 assert c.get('/api/reports/attendance',headers=m,params={'start':'not-a-date'}).status_code==422
 assert c.get('/api/reports/attendance',headers=auth('9000000001')).status_code==403

def test_bulk_csv_preview_commit_and_pin_change():
 m=auth('9000000000')
 from io import BytesIO
 bad=b'full_name,phone,license_number,vehicle_type,vehicle_number,shift_start,shift_end\nJane Driver,9898989898,BAD,Truck,KA01AB1234,09:00,18:00\n'
 r=c.post('/api/drivers/import-preview',files={'file':('drivers.csv',BytesIO(bad),'text/csv')},headers=m)
 assert r.status_code==200,r.text
 assert r.json()['invalid']==1
 assert c.post('/api/drivers/import-commit',files={'file':('drivers.csv',BytesIO(bad),'text/csv')},headers=m).status_code==422
 good=b'full_name,phone,license_number,vehicle_type,vehicle_number,shift_start,shift_end\nJane Driver,9898989898,KA0120230001234,Truck,KA01AB1234,09:00,18:00\n'
 r=c.post('/api/drivers/import-preview',files={'file':('drivers.csv',BytesIO(good),'text/csv')},headers=m)
 assert r.status_code==200 and r.json()['valid']==1,r.text
 r=c.post('/api/drivers/import-commit',files={'file':('drivers.csv',BytesIO(good),'text/csv')},headers=m)
 assert r.status_code==200,r.text
 temp=r.json()['credentials_once'][0]['temporary_pin']
 r=c.post('/api/auth/login',json={'phone':'9898989898','pin':temp})
 assert r.status_code==200,r.text
 assert r.json()['enrollment_only'] is True and r.json()['user']['pin_change_required'] is True
 enrollment={'Authorization':'Bearer '+r.json()['access_token']}
 r=c.post('/api/me/change-pin',headers=enrollment,json={'old_pin':temp,'new_pin':'verySecure123'})
 assert r.status_code==200,r.text
 r=c.post('/api/auth/login',json={'phone':'9898989898','pin':'verySecure123'})
 assert r.status_code==200 and r.json()['user']['pin_change_required'] is False
 assert c.post('/api/drivers/import-commit',files={'file':('drivers.csv',BytesIO(good),'text/csv')},headers=m).status_code==422

def test_attendance_pdf_download():
 r=c.get('/api/reports/attendance.pdf',headers=auth('9000000000'))
 assert r.status_code==200,r.text
 assert r.headers['content-type'].startswith('application/pdf')
 assert r.content.startswith(b'%PDF')

def test_distinct_sos_incidents_acknowledgement_and_details():
 m=auth('9000000000');d=auth('9000000001')
 first=c.post('/api/sos',json={'confirmed':True,'lat':12.98,'lng':77.60,'message':'Vehicle stalled'},headers=d)
 second=c.post('/api/sos',json={'confirmed':True,'lat':12.99,'lng':77.61,'message':'Medical assistance'},headers=d)
 assert first.status_code==200 and second.status_code==200
 assert first.json()['id']!=second.json()['id']
 items=c.get('/api/alerts',headers=m).json()
 a=next(a for a in items if a['id']==second.json()['id'])
 assert a['kind']=='sos' and a['status']=='open'
 assert a['driver_name']=='Arjun Kumar' and a['driver_phone']=='9000000001' and a['vehicle']=='Truck'
 assert a['lat']==12.99 and a['lng']==77.61
 assert c.patch('/api/alerts/'+a['id'],json={'status':'acknowledged'},headers=d).status_code==403
 assert c.patch('/api/alerts/'+a['id'],json={'status':'acknowledged'},headers=m).status_code==200
 assert c.patch('/api/alerts/'+a['id'],json={'status':'resolved'},headers=m).status_code==200
 assert c.patch('/api/alerts/'+a['id'],json={'status':'acknowledged'},headers=m).status_code==409

def test_driver_self_service_pin_and_face_photo():
 from io import BytesIO
 from PIL import Image
 d=auth('9000000001')
 assert c.post('/api/me/change-pin',headers=d,json={'old_pin':'0000','new_pin':'987654'}).status_code==403
 assert c.post('/api/me/change-pin',headers=d,json={'old_pin':'1234','new_pin':'987654'}).status_code==200
 assert c.post('/api/auth/login',json={'phone':'9000000001','pin':'1234'}).status_code==401
 assert c.post('/api/auth/login',json={'phone':'9000000001','pin':'987654'}).status_code==200
 im=Image.new('RGB',(80,80),'blue');b=BytesIO();im.save(b,'PNG')
 enrolled=c.post('/api/face/enroll',headers=d,files={'image':('face.png',b.getvalue(),'image/png')})
 assert enrolled.status_code==200,enrolled.text
 assert enrolled.json()['verification_status']=='pending_external_biometric_verification'
 assert c.get('/api/me',headers=d).json()['face_enrolled'] is True

def test_manager_face_photo_review_lifecycle():
 from io import BytesIO
 from PIL import Image
 m=auth('9000000000')
 login=c.post('/api/auth/login',json={'phone':'9000000001','pin':'987654'})
 assert login.status_code==200
 d={'Authorization':'Bearer '+login.json()['access_token']}
 me=c.get('/api/me',headers=d).json()
 assert me['face_review_status']=='pending'
 im=Image.new('RGB',(80,80),'green');b=BytesIO();im.save(b,'PNG')
 payload={'image':('face.png',b.getvalue(),'image/png')}
 assert c.post('/api/face/enroll',headers=d,files=payload).status_code==409
 good=c.patch('/api/drivers/driver-demo/face-review',headers=m,json={'approved':True})
 assert good.status_code==200,good.text
 assert good.json()['face_review_status']=='approved'
 assert c.post('/api/face/enroll',headers=d,files=payload).status_code==409
 reject=c.patch('/api/drivers/driver-demo/face-review',headers=m,json={'approved':False,'review_note':'Photo not clear'})
 assert reject.status_code==200
 assert reject.json()['face_review_status']=='rejected'
 again=c.post('/api/face/enroll',headers=d,files=payload)
 assert again.status_code==200,again.text
 assert c.get('/api/me',headers=d).json()['face_review_status']=='pending'
