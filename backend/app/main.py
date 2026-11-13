"""KRIYA360 demo API. PostgreSQL-ready; SQLite used out of the box.
Production requires TLS, secure secrets, rate-limits, verified SMS and biometric service.
"""
from __future__ import annotations
import math, os, secrets, time, uuid, hashlib, re, json, csv, io
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Optional
import httpx, jwt
from fastapi import FastAPI, Depends, HTTPException, Header, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, String, Integer, Float, Boolean, DateTime, ForeignKey, Text, select, func, text as sqltext, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session
from sqlalchemy.pool import StaticPool
from hashlib import pbkdf2_hmac

HERE=Path(__file__).resolve().parent.parent
UPLOAD=HERE/'uploads'; UPLOAD.mkdir(exist_ok=True)
DATABASE_URL=os.getenv('DATABASE_URL', f'sqlite:///{HERE / "kriya360.db"}')
JWT_SECRET=os.getenv('JWT_SECRET','DEMO-ONLY-CHANGE-THIS-SECRET-AT-LEAST-32-BYTES')
DEMO=os.getenv('DEMO_SEED','true').lower()=='true'
kwargs={'connect_args':{'check_same_thread':False}} if DATABASE_URL.startswith('sqlite') else {}
if DATABASE_URL=='sqlite://': kwargs={'connect_args':{'check_same_thread':False},'poolclass':StaticPool}
engine=create_engine(DATABASE_URL, **kwargs)
SessionLocal=sessionmaker(bind=engine,expire_on_commit=False)
class Base(DeclarativeBase): pass
class User(Base):
 __tablename__='users'
 id=Column(String,primary_key=True); role=Column(String,nullable=False); name=Column(String,nullable=False); phone=Column(String,unique=True,nullable=False); pin_hash=Column(String,nullable=False); email=Column(String,nullable=True,unique=True); password_hash=Column(String,nullable=True)
 language=Column(String,default='en'); license_no=Column(String,default=''); vehicle=Column(String,default=''); vehicle_plate=Column(String,default=''); face_path=Column(String,default=''); license_path=Column(String,default=''); approved=Column(Boolean,default=True)
 shift_start=Column(DateTime(timezone=True)); shift_end=Column(DateTime(timezone=True)); lat=Column(Float); lng=Column(Float); last_gps=Column(DateTime(timezone=True)); last_gps_received_at=Column(DateTime(timezone=True)); last_vehicle=Column(String,default='')
 pin_change_required=Column(Boolean,default=False); shift_expected=Column(String,default='09:00'); shift_end_expected=Column(String,default='18:00'); license_verified=Column(Boolean,default=False); license_review_note=Column(String,default=''); license_inspected_at=Column(DateTime(timezone=True)); license_inspected_by=Column(String,default=''); active=Column(Boolean,default=True); face_review_status=Column(String,default='not_submitted'); face_review_note=Column(String,default='')
class Task(Base):
 __tablename__='tasks'
 id=Column(String,primary_key=True); title=Column(String,nullable=False); address=Column(String,nullable=False); lat=Column(Float,nullable=False); lng=Column(Float,nullable=False)
 driver_id=Column(String,ForeignKey('users.id')); status=Column(String,default='assigned'); priority=Column(String,default='normal'); customer=Column(String,default=''); customer_phone=Column(String,default='')
 instructions=Column(Text,default=''); due_at=Column(DateTime(timezone=True)); assigned_at=Column(DateTime(timezone=True)); started_at=Column(DateTime(timezone=True)); completed_at=Column(DateTime(timezone=True)); proof_path=Column(String,default=''); otp_hash=Column(String,default=''); otp_expires=Column(DateTime(timezone=True)); otp_verified=Column(Boolean,default=False); otp_attempts=Column(Integer,default=0)
 late_reason=Column(Text,default=''); late_reason_at=Column(DateTime(timezone=True)); route_json=Column(Text,default=''); route_alternatives_json=Column(Text,default='[]'); route_distance_km=Column(Float,default=0); route_duration_min=Column(Float,default=0); route_source=Column(String,default=''); route_deviation=Column(Boolean,default=False)
class GPS(Base):
 __tablename__='gps'
 id=Column(String,primary_key=True); driver_id=Column(String,ForeignKey('users.id')); task_id=Column(String); lat=Column(Float); lng=Column(Float); at=Column(DateTime(timezone=True)); accuracy_m=Column(Float); speed_mps=Column(Float); captured_at=Column(DateTime(timezone=True)); sample_id=Column(String)
class Expense(Base):
 __tablename__='expenses'
 id=Column(String,primary_key=True); driver_id=Column(String,ForeignKey('users.id')); task_id=Column(String,ForeignKey('tasks.id')); category=Column(String); amount=Column(Float); note=Column(Text,default=''); receipt_path=Column(String,default=''); evidence_sha=Column(String,default=''); evidence_visual=Column(String,default=''); fraud_flags=Column(Text,default='[]'); evidence_reviewed=Column(Boolean,default=False); reviewed_at=Column(DateTime(timezone=True)); status=Column(String,default='pending'); created_at=Column(DateTime(timezone=True))
class Alert(Base):
 __tablename__='alerts'
 id=Column(String,primary_key=True); kind=Column(String); severity=Column(String,default='warning'); driver_id=Column(String); task_id=Column(String); message=Column(String); status=Column(String,default='open'); at=Column(DateTime(timezone=True)); lat=Column(Float); lng=Column(Float)
class Attendance(Base):
 __tablename__='attendance'
 id=Column(String,primary_key=True); driver_id=Column(String); kind=Column(String); at=Column(DateTime(timezone=True)); lat=Column(Float); lng=Column(Float); vehicle=Column(String,default=''); attendance_type=Column(String,default='office'); distance_from_office_m=Column(Float); gps_accuracy_m=Column(Float); verification_state=Column(String,default='not_configured')
class OfficeGeofence(Base):
 """Single authoritative office attendance location, managed from the dashboard."""
 __tablename__='office_geofence'
 id=Column(String,primary_key=True)
 lat=Column(Float,nullable=False); lng=Column(Float,nullable=False)
 radius_m=Column(Float,nullable=False,default=150)
 max_accuracy_m=Column(Float,nullable=False,default=75)
 enabled=Column(Boolean,nullable=False,default=False)
 updated_at=Column(DateTime(timezone=True)); updated_by=Column(String)
class OfficeGeofenceChange(Base):
 __tablename__='office_geofence_changes'
 id=Column(String,primary_key=True)
 updated_at=Column(DateTime(timezone=True),nullable=False)
 updated_by=Column(String,nullable=False)
 lat=Column(Float,nullable=False); lng=Column(Float,nullable=False)
 radius_m=Column(Float,nullable=False); max_accuracy_m=Column(Float,nullable=False)
 enabled=Column(Boolean,nullable=False)
Base.metadata.create_all(engine)
# Non-destructive additive migration for databases created by earlier KRIYA360 versions.
# Back up the SQLite file before deployment; no existing rows are removed.
with engine.begin() as connection:
 for table, additions in {
  'users': {'last_gps_received_at':'TIMESTAMP','email':'VARCHAR','password_hash':'VARCHAR','pin_change_required':'BOOLEAN DEFAULT 0','shift_end_expected':"VARCHAR DEFAULT '18:00'",'license_path':'VARCHAR','license_verified':'BOOLEAN DEFAULT 0','license_review_note':"VARCHAR DEFAULT ''",'license_inspected_at':'DATETIME','license_inspected_by':"VARCHAR DEFAULT ''",'active':'BOOLEAN DEFAULT 1','face_review_status':"VARCHAR DEFAULT 'not_submitted'",'face_review_note':"VARCHAR DEFAULT ''"},
  'tasks': {'route_alternatives_json':"TEXT DEFAULT '[]'",'late_reason':"TEXT DEFAULT ''",'late_reason_at':'DATETIME','otp_attempts':'INTEGER DEFAULT 0'},
  'attendance': {'attendance_type':"VARCHAR DEFAULT 'office'",'distance_from_office_m':'FLOAT','gps_accuracy_m':'FLOAT','verification_state':"VARCHAR DEFAULT 'not_configured'"},
  'gps': {'accuracy_m':'FLOAT','speed_mps':'FLOAT','captured_at':'TIMESTAMP','sample_id':'VARCHAR'},
  'expenses': {'evidence_sha':'VARCHAR','evidence_visual':'VARCHAR','fraud_flags':"TEXT DEFAULT '[]'",'evidence_reviewed':'BOOLEAN DEFAULT 0','reviewed_at':'DATETIME'}
 }.items():
  existing={c['name'] for c in inspect(connection).get_columns(table)}
  for column, sqltype in additions.items():
   if column not in existing: connection.execute(sqltext(f'ALTER TABLE {table} ADD COLUMN {column} {sqltype}'))
app=FastAPI(title='KRIYA360 Operations API',version='0.1.0-demo')
app.add_middleware(CORSMiddleware,allow_origins=os.getenv('CORS_ORIGINS','http://localhost:5173,http://127.0.0.1:5173').split(','),allow_credentials=True,allow_methods=['*'],allow_headers=['*'])

def now(): return datetime.now(timezone.utc)
def naive(t): return t.replace(tzinfo=None) if t else None
def hash_pin(pin):
 salt=secrets.token_bytes(16); return salt.hex()+':'+pbkdf2_hmac('sha256',pin.encode(),salt,180000).hex()
def check_pin(pin,stored):
 try:
  salt,digest=stored.split(':'); return secrets.compare_digest(pbkdf2_hmac('sha256',pin.encode(),bytes.fromhex(salt),180000).hex(),digest)
 except Exception:return False
def db():
 with SessionLocal() as s: yield s
def err(code,msg): raise HTTPException(status_code=code,detail=msg)
def require(authorization:Optional[str]=Header(None),s:Session=Depends(db)):
 if not authorization or not authorization.startswith('Bearer '):err(401,'Login required')
 try: body=jwt.decode(authorization[7:],JWT_SECRET,algorithms=['HS256']); uid=body['sub']
 except Exception:err(401,'Invalid or expired token')
 if body.get('scope')=='enrollment':err(403,'Enrollment token cannot access driver or manager APIs')
 u=s.get(User,uid)
 if not u or not u.active or not u.approved:err(403,'Account not approved or inactive')
 if u.role=='driver' and not u.license_verified:err(403,'Driving licence verification required before driver access')
 return u
def manager(u=Depends(require)):
 if u.role not in ('manager','super_admin'):err(403,'Management access required')
 return u
def super_admin(u=Depends(require)):
 if u.role!='super_admin':err(403,'Super admin access required')
 return u
def driver(u=Depends(require)):
 if u.role!='driver':err(403,'Driver only')
 return u
def token(u):return jwt.encode({'sub':u.id,'role':u.role,'exp':now()+timedelta(hours=12)},JWT_SECRET,algorithm='HS256')
def iso(d): return d.isoformat()+'Z' if d and d.tzinfo is None else d.isoformat() if d else None

def license_status(u):
 note=(u.license_review_note or '').strip().lower()
 if u.approved and u.license_verified:
  return 'approved'
 if not u.license_path:
  return 'missing'
 if 'rejected' in note or 'upload again' in note or 're-upload' in note:
  return 'rejected'
 return 'pending'

def license_upload_locked(u):
 return license_status(u) in ('pending','approved')

def safe_user(u):return {'id':u.id,'role':u.role,'name':u.name,'phone':u.phone,'email':u.email if u.role in ('manager','super_admin') else None,'language':u.language,'license_no':u.license_no,'vehicle':u.vehicle,'vehicle_plate':u.vehicle_plate,'face_enrolled':bool(u.face_path),'face_review_status':('approved' if u.face_review_status=='approved' else 'rejected' if u.face_review_status=='rejected' else 'pending' if u.face_path else 'not_submitted'),'face_review_note':u.face_review_note or '', 'face_url':'/api/files/'+Path(u.face_path).name if u.face_path else None,'license_url':'/api/files/'+Path(u.license_path).name if u.license_path else None,'approved':u.approved,'active':u.active is not False,'license_verified':bool(u.license_verified),'license_review_note':u.license_review_note or '','license_status':license_status(u),'license_inspected_at':iso(u.license_inspected_at),'on_shift':bool(u.shift_start and (not u.shift_end or naive(u.shift_start)>naive(u.shift_end))),'lat':u.lat,'lng':u.lng,'last_gps':iso(u.last_gps),'shift_expected':u.shift_expected,'shift_end_expected':u.shift_end_expected,'pin_change_required':bool(u.pin_change_required)}
def task_json(t,s):
 d=s.get(User,t.driver_id) if t.driver_id else None
 return {'id':t.id,'title':t.title,'address':t.address,'lat':t.lat,'lng':t.lng,'driver_id':t.driver_id,'driver_name':d.name if d else None,'status':t.status,'priority':t.priority,'customer':t.customer,'customer_phone':t.customer_phone,'instructions':t.instructions,'due_at':iso(t.due_at),'assigned_at':iso(t.assigned_at),'started_at':iso(t.started_at),'completed_at':iso(t.completed_at),'proof_url':('/api/files/'+Path(t.proof_path).name) if t.proof_path else None,'otp_verified':t.otp_verified,'route_distance_km':t.route_distance_km,'route_duration_min':t.route_duration_min,'route_source':t.route_source,'route_available':bool(t.route_json and (t.route_source or '').startswith(('OSRM','TomTom'))),'route_deviation':t.route_deviation,'late_reason':t.late_reason or '','late_reason_at':iso(t.late_reason_at)}
def expense_json(e,s):
 u=s.get(User,e.driver_id)
 return {'id':e.id,'driver_id':e.driver_id,'driver_name':u.name if u else '', 'task_id':e.task_id,'category':e.category,'amount':e.amount,'note':e.note,'status':e.status,'created_at':iso(e.created_at),'receipt_url':'/api/files/'+Path(e.receipt_path).name if e.receipt_path else None,'fraud_flags':__import__('json').loads(e.fraud_flags or '[]'),'evidence_reviewed':bool(e.evidence_reviewed),'reviewed_at':iso(e.reviewed_at)}
def alert_json(a,s):
 u=s.get(User,a.driver_id) if a.driver_id else None
 return {'id':a.id,'kind':a.kind,'severity':a.severity,'driver_id':a.driver_id,'driver_name':u.name if u else '', 'driver_phone':u.phone if u else '', 'vehicle':u.vehicle if u else '', 'vehicle_plate':u.vehicle_plate if u else '', 'task_id':a.task_id,'message':a.message,'status':a.status,'at':iso(a.at),'lat':a.lat,'lng':a.lng}
def new_alert(s,kind,driver_id,message,task_id=None,severity='warning',lat=None,lng=None):
 existing=s.scalar(select(Alert).where(Alert.kind==kind,Alert.driver_id==driver_id,Alert.task_id==task_id,Alert.status=='open'))
 if existing:return existing
 a=Alert(id=str(uuid.uuid4()),kind=kind,driver_id=driver_id,task_id=task_id,message=message,severity=severity,at=now(),lat=lat,lng=lng);s.add(a);return a

def haversine(a,b,c,d):
 r=6371.;p1,p2=math.radians(a),math.radians(c);dl=math.radians(d-b);dp=p2-p1
 return 2*r*math.asin(math.sqrt(math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2))
def line_distance_km(lat,lng,coordinates):
 if not coordinates:return 0
 # Coordinates in [longitude, latitude] format; measure to polyline segments approximately in metres.
 x=lng*111320*math.cos(math.radians(lat));y=lat*111320
 dist=float('inf')
 for p,q in zip(coordinates,coordinates[1:]):
  ax=p[0]*111320*math.cos(math.radians(lat));ay=p[1]*111320;bx=q[0]*111320*math.cos(math.radians(lat));by=q[1]*111320
  dx=bx-ax;dy=by-ay;z=max(0,min(1,((x-ax)*dx+(y-ay)*dy)/(dx*dx+dy*dy))) if dx*dx+dy*dy else 0
  dist=min(dist,math.hypot(x-(ax+z*dx),y-(ay+z*dy)))
 return dist/1000
async def tomtom_route(a,b,c,d,route_type='fastest'):
 """Opt-in traffic-aware road routing; requires TOMTOM_API_KEY and provider terms."""
 key=os.getenv('TOMTOM_API_KEY','').strip()
 if not key:return None
 url=f'https://api.tomtom.com/routing/1/calculateRoute/{a},{b}:{c},{d}/json'
 async with httpx.AsyncClient(timeout=12) as client:
  response=await client.get(url,params={'key':key,'traffic':'true','routeType':route_type,'maxAlternatives':2,'computeTravelTimeFor':'all'})
  response.raise_for_status()
  routes=response.json().get('routes',[])
  if not routes:raise ValueError('No routes returned from traffic provider')
  def convert(item):
   summary=item['summary']
   points=[point for leg in item.get('legs',[]) for point in leg.get('points',[])]
   coords=[[float(v['longitude']),float(v['latitude'])] for v in points]
   if len(coords)<2:raise ValueError('Traffic provider returned no road geometry')
   return {'distance_km':round(summary['lengthInMeters']/1000,2),
           'duration_min':round(summary['travelTimeInSeconds']/60,1),
           'coordinates':coords,'steps':[],
           'traffic_delay_min':round(summary.get('trafficDelayInSeconds',0)/60,1),
           'source':'TomTom traffic-aware routing','traffic_aware':True}
  primary=convert(routes[0]);primary['alternative_routes']=[]
  for candidate in routes[1:]:
   try:primary['alternative_routes'].append(convert(candidate))
   except (ValueError,KeyError,TypeError):pass
  return primary

async def route_options(a,b,c,d,mode='fastest'):
 if mode not in ('fastest','shortest'):err(422,'mode must be fastest or shortest')
 if os.getenv('TOMTOM_API_KEY','').strip():
  try:return await tomtom_route(a,b,c,d,mode)
  except (httpx.HTTPError,ValueError,KeyError,TypeError):
   # Fall back but never label estimated speed as current traffic.
   pass
 result=await route_between(a,b,c,d)
 result['requested_mode']=mode
 result['shortest_guaranteed']=False
 result['notice']='Traffic data unavailable; this route does not account for live traffic.'
 return result

@app.get('/api/routing/options')
async def routing_options(from_lat:float,from_lng:float,to_lat:float,to_lng:float,mode:str='fastest',_=Depends(manager)):
 for lat,lng in ((from_lat,from_lng),(to_lat,to_lng)):
  if not (-90<=lat<=90 and -180<=lng<=180):err(422,'Invalid coordinates')
 return await route_options(from_lat,from_lng,to_lat,to_lng,mode)

async def route_between(a,b,c,d):
 """OSRM public demo API for development ONLY; fallback clearly marked straight-line estimate."""
 url=f'https://router.project-osrm.org/route/v1/driving/{b},{a};{d},{c}'
 try:
  async with httpx.AsyncClient(timeout=5) as client:
   result=(await client.get(url,params={'overview':'full','geometries':'geojson','steps':'true'})).json()
  r=result['routes'][0]
  directions=[]
  for leg in r.get('legs',[]):
   for step in leg.get('steps',[]):
    maneuver=step.get('maneuver',{});street=step.get('name') or step.get('ref') or 'unnamed road'
    directions.append({'instruction':f"{maneuver.get('type','Continue').replace('_',' ').capitalize()} {maneuver.get('modifier','').replace('_',' ')} on {street}".strip(),'distance_m':round(step.get('distance',0)),'duration_sec':round(step.get('duration',0)),'location':maneuver.get('location',[])})
  return {'distance_km':round(r['distance']/1000,2),'duration_min':round(r['duration']/60,1),'coordinates':r['geometry']['coordinates'],'steps':directions,'source':'OSRM demo road routing','traffic_aware':False,'alternative_routes':[]}
 except Exception:
  km=haversine(a,b,c,d);return {'distance_km':round(km,2),'duration_min':round(km/30*60,1),'coordinates':[[b,a],[d,c]],'steps':[],'source':'straight-line fallback (not road navigation)','traffic_aware':False,'alternative_routes':[]}

class Login(BaseModel):phone:str;pin:str
class AdminLogin(BaseModel):
 email:str
 password:str
class AdminSetup(BaseModel):
 phone:str
 pin:str
 email:str
 password:str
 setup_key:str
EMAIL_RE=re.compile(r"^[^\s@]+@[^\s@]+\.[A-Za-z]{2,}$")
def normalized_email(value):
 email=(value or '').strip().lower()
 if len(email)>254 or not EMAIL_RE.fullmatch(email):err(422,'Enter a valid email address')
 return email
def valid_password(value):
 if len(value or '')<12 or len(value)>128 or not re.search('[A-Za-z]',value) or not re.search('[0-9]',value):err(422,'Password must be 12-128 characters and contain letters and numbers')

class DriverCreate(BaseModel):name:str;phone:str;pin:str=Field(min_length=4,max_length=12);license_no:str='';vehicle:str='';vehicle_plate:str='';language:str='en';shift_expected:str='09:00'
class TaskCreate(BaseModel):title:str;driver_id:str;address:str;lat:float;lng:float;due_at:datetime;priority:str='normal';customer:str='';customer_phone:str='';instructions:str=''
class Coords(BaseModel):
 lat:float=Field(ge=-90,le=90)
 lng:float=Field(ge=-180,le=180)
 task_id:Optional[str]=None
 accuracy_m:Optional[float]=Field(default=None,ge=0,le=10000)
 speed_mps:Optional[float]=Field(default=None,ge=0,le=150)
 captured_at:Optional[datetime]=None
 sample_id:Optional[str]=Field(default=None,min_length=8,max_length=100)
class Punch(Coords):vehicle:str=''
class OfficeGeofenceUpdate(BaseModel):
 lat:float=Field(ge=-90,le=90)
 lng:float=Field(ge=-180,le=180)
 radius_m:float=Field(ge=30,le=2000)
 max_accuracy_m:float=Field(ge=5,le=500)
 enabled:bool=False
class ExpenseCreate(BaseModel):task_id:str;category:str;amount:float=Field(gt=0);note:str=''
class SOSCreate(BaseModel):confirmed:bool;lat:Optional[float]=None;lng:Optional[float]=None;message:str='Emergency assistance requested'
class StatusUpdate(BaseModel):status:str
class LanguageUpdate(BaseModel):language:str
class VerifyOTP(BaseModel):otp:str
class DriverReview(BaseModel):approved:bool;license_matches:bool=False;review_note:str=''
class DriverProfile(BaseModel):name:str=Field(min_length=2,max_length=120);license_no:str=Field(min_length=3,max_length=80);vehicle:str='';vehicle_plate:str='';phone:Optional[str]=None
class ManagerDriverEdit(BaseModel):name:str=Field(min_length=2,max_length=120);phone:str;license_no:str;vehicle:str='';vehicle_plate:str='';shift_expected:str='09:00';active:bool=True
class LateReason(BaseModel):reason:str=Field(min_length=5,max_length=600)


# Standard Indian DL format after removing spaces/hyphens: state (2), RTO (2), issue year (4), serial (7).
# Regional/legacy formats may differ; manager review is still mandatory.
DL_RE=re.compile(r'^[A-Z]{2}[0-9]{2}(?:19|20)[0-9]{2}[0-9]{7}$')
def normalized_dl(value):return re.sub(r'[\s-]','',value or '').upper()
def check_dl(value):
 if not DL_RE.fullmatch(normalized_dl(value)):err(422,'Licence format expected: KA0120230001234 (state, RTO, year, 7-digit serial)')
def check_phone(value):
 if not re.fullmatch(r'[6-9][0-9]{9}',value or ''):err(422,'Enter a valid 10-digit Indian mobile number')
def check_shift(value):
 if not re.fullmatch(r'(?:[01][0-9]|2[0-3]):[0-5][0-9]',value or ''):err(422,'Shift must be HH:MM')

@app.get('/api/health')
def health():return {'ok':True,'service':'KRIYA360','time':iso(now())}
@app.post('/api/auth/login')
def login(x:Login,s:Session=Depends(db)):
 u=s.scalar(select(User).where(User.phone==x.phone))
 if not u or u.role!='driver' or not check_pin(x.pin,u.pin_hash):err(401,'Invalid driver phone or PIN')
 if u.active is False:err(403,'Account suspended')
 if u.role=='driver' and (not u.approved or not u.license_verified):
  limited=jwt.encode({'sub':u.id,'scope':'enrollment','exp':now()+timedelta(hours=24)},JWT_SECRET,algorithm='HS256')
  return {'access_token':limited,'enrollment_only':True,'user':safe_user(u)}
 if not u.approved:err(403,'Account awaiting approval')
 return {'access_token':token(u),'user':safe_user(u)}
@app.post('/api/auth/admin/login')
def admin_login(x:AdminLogin,s:Session=Depends(db)):
 email=normalized_email(x.email)
 u=s.scalar(select(User).where(User.email==email,User.role.in_(['manager','super_admin'])))
 if not u or not u.password_hash or not check_pin(x.password,u.password_hash):err(401,'Invalid admin email or password')
 if not u.active:err(403,'Account suspended')
 return {'access_token':token(u),'user':safe_user(u)}

@app.post('/api/auth/admin/setup')
def admin_setup(x:AdminSetup,s:Session=Depends(db)):
 """One-time legacy credential migration. Never allow takeover of configured accounts."""
 email=normalized_email(x.email)
 valid_password(x.password)
 expected=os.getenv('ADMIN_SETUP_KEY','')
 if len(expected)<24 or not secrets.compare_digest(x.setup_key,expected):err(403,'Administrator migration key is required')
 u=s.scalar(select(User).where(User.phone==x.phone,User.role=='manager'))
 if not u or not u.active or u.password_hash or not check_pin(x.pin,u.pin_hash):err(403,'Account cannot be migrated with supplied credentials')
 if s.scalar(select(User).where(User.email==email)):err(409,'Email already in use')
 u.email=email;u.password_hash=hash_pin(x.password);s.commit()
 return {'access_token':token(u),'user':safe_user(u)}

@app.get('/api/me')
def me(u=Depends(require)):return safe_user(u)
@app.patch('/api/me/language')
def set_language(x:LanguageUpdate,u=Depends(require),s:Session=Depends(db)):
 if x.language not in ('en','hi','kn','ta','te'):err(400,'Unsupported language')
 u.language=x.language;s.commit();return safe_user(u)
@app.post('/api/auth/register-driver')
def public_driver_registration_disabled():err(403,'Registration is management-only. Ask your manager to create a driver account.')


def onboarding_user(authorization:Optional[str]=Header(None),s:Session=Depends(db)):
 if not authorization or not authorization.startswith('Bearer '):err(401,'Enrollment token required')
 try:
  body=jwt.decode(authorization[7:],JWT_SECRET,algorithms=['HS256'])
  if body.get('scope')!='enrollment':err(403,'Not an enrollment token')
 except Exception:err(401,'Invalid or expired enrollment token')
 u=s.get(User,body['sub'])
 if not u or u.role!='driver':err(404,'Driver not found')
 return u

@app.get('/api/onboarding/status')
def onboarding_status(u=Depends(onboarding_user)):return safe_user(u)

@app.post('/api/onboarding/{kind}')
async def onboarding_upload(kind:str,image:UploadFile=File(...),u=Depends(onboarding_user),s:Session=Depends(db)):
 if kind not in ('license','face'):err(400,'Upload a driving licence or live face photograph')
 if kind=='face':
  if u.face_path and u.face_review_status!='rejected':err(409,'Face photo already submitted for review')
  path=await store_image(image)
  u.face_path=str(path);u.face_review_status='pending';u.face_review_note='Awaiting manager review of live camera enrolment'
  s.commit()
  return {'kind':'face','uploaded':True,'face_review_status':'pending','biometric_verified':False}
 if license_upload_locked(u):err(409,'Licence proof already submitted. Wait for manager review before uploading again.')
 path=await store_image(image)
 u.license_path=str(path);u.license_verified=False;u.approved=False;u.license_inspected_at=None;u.license_inspected_by='';u.license_review_note='Licence proof uploaded and awaiting management review'
 s.commit();return {'kind':kind,'uploaded':True,'verified':False,'license_status':license_status(u)}

@app.patch('/api/drivers/{uid}/approval')
def driver_approval(uid:str,x:DriverReview,s:Session=Depends(db),_=Depends(manager)):
 u=s.get(User,uid)
 if not u or u.role!='driver':err(404,'Driver not found')
 if x.approved:
  if not u.license_no or not u.license_path:err(409,'Driving licence image is required before approval')
  if not u.face_path or u.face_review_status!='approved':err(409,'Manager-approved live face enrolment is required before driver activation')
  check_dl(u.license_no)
  if not u.license_inspected_at:err(409,'Open the uploaded licence image in the management dashboard before approval')
  if not x.license_matches:err(409,'Manager must inspect the licence image and confirm its number matches the typed value')
  u.license_verified=True;u.approved=True;u.license_review_note=x.review_note or 'Manager verified the licence proof'
 else:
  u.license_verified=False;u.approved=False;u.license_review_note=x.review_note or 'Rejected. Please upload licence proof again.'
  if 'rejected' not in u.license_review_note.lower():
   u.license_review_note='Rejected: '+u.license_review_note
 u.license_inspected_at=now();u.license_inspected_by=_.id;s.commit();return safe_user(u)

@app.patch('/api/drivers/{uid}')
def edit_driver(uid:str,x:ManagerDriverEdit,s:Session=Depends(db),_=Depends(manager)):
 u=s.get(User,uid)
 if not u or u.role!='driver':err(404,'Driver not found')
 check_phone(x.phone);check_dl(x.license_no);check_shift(x.shift_expected)
 if x.vehicle and x.vehicle not in ('Lorry','Truck','Heavy Truck','Container Truck'):err(422,'Invalid vehicle type')
 if not x.active and s.scalar(select(Task).where(Task.driver_id==uid,Task.status.in_(['assigned','in_progress']))):err(409,'Finish or reassign active deliveries before deactivation')
 taken=s.scalar(select(User).where(User.phone==x.phone,User.id!=uid))
 if taken:err(409,'Phone number already used')
 changed=normalized_dl(u.license_no)!=normalized_dl(x.license_no)
 u.name=x.name.strip();u.phone=x.phone;u.license_no=normalized_dl(x.license_no);u.vehicle=x.vehicle;u.vehicle_plate=x.vehicle_plate;u.shift_expected=x.shift_expected;u.active=x.active
 if changed:u.license_verified=False;u.license_inspected_at=None;u.license_inspected_by='';u.license_review_note='Licence number edited; requires new number-match verification'
 s.commit();return safe_user(u)

@app.delete('/api/drivers/{uid}')
def deactivate_driver(uid:str,s:Session=Depends(db),_=Depends(manager)):
 u=s.get(User,uid)
 if not u or u.role!='driver':err(404,'Driver not found')
 if s.scalar(select(Task).where(Task.driver_id==uid,Task.status.in_(['assigned','in_progress']))):err(409,'Reassign or finish active deliveries before deactivating driver')
 u.active=False;s.commit();return {'deactivated':True,'driver_id':uid}

@app.patch('/api/me/profile')
def profile_edit(x:DriverProfile,u=Depends(driver),s:Session=Depends(db)):
 check_dl(x.license_no)
 if x.phone is not None:check_phone(x.phone)
 if x.vehicle and x.vehicle not in ('Lorry','Truck','Heavy Truck','Container Truck'):err(400,'Vehicle type must be a truck or lorry')
 if x.phone and x.phone!=u.phone:
  if s.scalar(select(User).where(User.phone==x.phone)):err(409,'Phone already used')
  u.phone=x.phone
 if normalized_dl(u.license_no)!=normalized_dl(x.license_no):
  u.license_verified=False;u.license_inspected_at=None;u.license_inspected_by='';u.license_review_note='Driver edited licence number; awaiting manager re-verification'
 u.name=x.name.strip();u.license_no=normalized_dl(x.license_no);u.vehicle=x.vehicle;u.vehicle_plate=x.vehicle_plate;s.commit();return safe_user(u)

@app.post('/api/license/upload')
async def license_upload(image:UploadFile=File(...),u=Depends(driver),s:Session=Depends(db)):
 if license_upload_locked(u):err(409,'Licence proof already submitted. Wait for manager review before uploading again.')
 u.license_path=str(await store_image(image));u.license_verified=False;u.approved=False;u.license_inspected_at=None;u.license_inspected_by='';u.license_review_note='Licence proof uploaded and awaiting management review';s.commit();return safe_user(u)

@app.post('/api/drivers')
def create_driver(x:DriverCreate,s:Session=Depends(db),_=Depends(manager)):
 check_phone(x.phone);check_dl(x.license_no);check_shift(x.shift_expected)
 if s.scalar(select(User).where(User.phone==x.phone)):err(409,'Phone already exists')
 if x.language not in ('en','hi','kn','ta','te'):err(400,'Unsupported language')
 if x.vehicle and x.vehicle not in ('Lorry','Truck','Heavy Truck','Container Truck'):err(400,'Vehicle must be lorry or truck')
 u=User(id=str(uuid.uuid4()),role='driver',name=x.name.strip(),phone=x.phone,pin_hash=hash_pin(x.pin),license_no=normalized_dl(x.license_no),vehicle=x.vehicle,vehicle_plate=x.vehicle_plate,language=x.language,shift_expected=x.shift_expected,approved=False,license_verified=False,active=True)
 s.add(u);s.commit();return safe_user(u)
@app.get('/api/drivers')
def drivers(s:Session=Depends(db),_=Depends(manager)):return [safe_user(u) for u in s.scalars(select(User).where(User.role=='driver')).all()]

@app.post('/api/face/enroll')
async def face_enroll(image:UploadFile=File(...),u=Depends(driver),s:Session=Depends(db)):
 # Manager review verifies submitted photo evidence, NOT biometric identity matching.
 if u.face_path and u.face_review_status != 'rejected':
  err(409,'Face photo already submitted; wait for review or ask management to reject for re-enrollment')
 path=await store_image(image)
 u.face_path=str(path);u.face_review_status='pending';u.face_review_note='Awaiting management face-photo review'
 s.commit()
 return {'enrolled':True,'face_review_status':'pending','verification_status':'pending_external_biometric_verification','biometric_verified':False}

class FaceReview(BaseModel):
 approved:bool
 review_note:str=Field(default='',max_length=500)

@app.patch('/api/drivers/{uid}/face-review')
def review_face_photo(uid:str,x:FaceReview,s:Session=Depends(db),_=Depends(manager)):
 u=s.get(User,uid)
 if not u or u.role!='driver':err(404,'Driver not found')
 if not u.face_path:err(409,'Driver has not submitted a face photo')
 u.face_review_status='approved' if x.approved else 'rejected'
 u.face_review_note=x.review_note.strip() or ('Manager visually reviewed uploaded face photograph' if x.approved else 'Rejected: retake and submit a clear face photograph')
 s.commit()
 return safe_user(u)
# Database-managed office geofence. A saved setting overrides the legacy environment
# variables. Legacy environment values remain a fallback until a manager saves a DB setting.
# A missing or invalid enabled configuration MUST fail closed, never allow punches.
def office_attendance_policy(s:Optional[Session]=None):
 if s is None:
  with SessionLocal() as session:
   return office_attendance_policy(session)
 saved=s.get(OfficeGeofence,'primary')
 if saved:
  return {'enabled':bool(saved.enabled),'configured':True,'source':'database',
          'lat':saved.lat,'lng':saved.lng,'radius_m':saved.radius_m,
          'max_accuracy_m':saved.max_accuracy_m,'updated_at':iso(saved.updated_at),
          'updated_by':saved.updated_by}
 enabled=os.getenv('OFFICE_GEOFENCE_ENABLED','false').strip().lower() in ('true','1','yes','on')
 if not enabled:return {'enabled':False}
 try:
  lat=float(os.environ['OFFICE_LATITUDE']);lng=float(os.environ['OFFICE_LONGITUDE'])
  radius=float(os.getenv('OFFICE_RADIUS_METERS','150'))
  max_accuracy=float(os.getenv('OFFICE_MAX_GPS_ACCURACY_METERS','75'))
  if not all(math.isfinite(v) for v in (lat,lng,radius,max_accuracy)) or not (-90<=lat<=90 and -180<=lng<=180 and 30<=radius<=2000 and 5<=max_accuracy<=500):raise ValueError('out of bounds')
 except (KeyError,ValueError,OverflowError):
  err(503,'Office attendance policy is not configured correctly; contact management')
 return {'enabled':True,'configured':True,'source':'legacy_environment','lat':lat,
         'lng':lng,'radius_m':radius,'max_accuracy_m':max_accuracy}

def _validate_office_settings(x:OfficeGeofenceUpdate):
 if not all(math.isfinite(v) for v in (x.lat,x.lng,x.radius_m,x.max_accuracy_m)):
  err(422,'Office latitude, longitude, radius and GPS accuracy must be finite numbers')

@app.get('/api/management/office-geofence')
def get_office_geofence(s:Session=Depends(db),_=Depends(manager)):
 return office_attendance_policy(s)

@app.put('/api/management/office-geofence')
def set_office_geofence(x:OfficeGeofenceUpdate,s:Session=Depends(db),u=Depends(super_admin)):
 _validate_office_settings(x)
 row=s.get(OfficeGeofence,'primary')
 if row is None:
  row=OfficeGeofence(id='primary');s.add(row)
 row.lat=x.lat;row.lng=x.lng;row.radius_m=x.radius_m
 row.max_accuracy_m=x.max_accuracy_m;row.enabled=x.enabled
 row.updated_at=now();row.updated_by=u.id
 s.add(OfficeGeofenceChange(id=str(uuid.uuid4()),updated_at=row.updated_at,
                            updated_by=u.id,lat=x.lat,lng=x.lng,
                            radius_m=x.radius_m,max_accuracy_m=x.max_accuracy_m,enabled=x.enabled))
 s.commit()
 return office_attendance_policy(s)

def office_distance_m(lat1,lng1,lat2,lng2):
 radius=6371008.8
 a=math.sin(math.radians(lat2-lat1)/2)**2+math.cos(math.radians(lat1))*math.cos(math.radians(lat2))*math.sin(math.radians(lng2-lng1)/2)**2
 return 2*radius*math.asin(min(1.0,math.sqrt(a)))

def classify_attendance(x,s:Session):
 """Office or remote based on DB geofence; never silently accept poor GPS.
 Biometric proof is intentionally NOT claimed by this GPS-only classification.
 """
 policy=office_attendance_policy(s)
 if not math.isfinite(x.lat) or not math.isfinite(x.lng):err(422,'Invalid GPS coordinates')
 # Preserve legacy demo/unconfigured attendance; NEVER label a location as Office
 # without an actual configured geofence and a sufficiently accurate GPS fix.
 if not policy.get('configured'):
  return ('unclassified',None)
 if x.accuracy_m is None or not math.isfinite(x.accuracy_m):err(422,'A precise GPS fix is required')
 accuracy_limit=policy.get('max_accuracy_m') or 75
 if x.accuracy_m>accuracy_limit:err(422,'GPS accuracy too low. Move outdoors and try again')
 distance=office_distance_m(x.lat,x.lng,policy['lat'],policy['lng'])
 in_office=distance+x.accuracy_m<=policy['radius_m']
 return ('office' if in_office else 'remote',round(distance,1))

@app.get('/api/attendance/office-policy')
def attendance_office_policy(s:Session=Depends(db),_=Depends(driver)):
 policy=office_attendance_policy(s)
 return {'enabled':policy['enabled'],'radius_m':policy.get('radius_m'),'max_accuracy_m':policy.get('max_accuracy_m')}

@app.post('/api/attendance/punch-in')
def punch_in(x:Punch,u=Depends(driver),s:Session=Depends(db)):
 attendance_type,office_distance=classify_attendance(x,s)
 if u.shift_start and (not u.shift_end or naive(u.shift_start)>naive(u.shift_end)):err(409,'Already punched in')
 u.shift_start=now();u.shift_end=None;u.lat=x.lat;u.lng=x.lng;u.last_gps=now();u.last_gps_received_at=now();u.last_vehicle=x.vehicle or u.vehicle
 s.add(Attendance(id=str(uuid.uuid4()),driver_id=u.id,kind='in',at=now(),lat=x.lat,lng=x.lng,vehicle=u.last_vehicle,attendance_type=attendance_type,distance_from_office_m=office_distance,gps_accuracy_m=x.accuracy_m,verification_state='not_configured'));s.commit();return safe_user(u)
@app.post('/api/attendance/punch-out')
def punch_out(x:Punch,u=Depends(driver),s:Session=Depends(db)):
 attendance_type,office_distance=classify_attendance(x,s)
 if not u.shift_start or (u.shift_end and naive(u.shift_end)>naive(u.shift_start)):err(409,'Not punched in')
 u.shift_end=now();u.lat=x.lat;u.lng=x.lng;u.last_gps=now();u.last_gps_received_at=now();s.add(Attendance(id=str(uuid.uuid4()),driver_id=u.id,kind='out',at=now(),lat=x.lat,lng=x.lng,vehicle=x.vehicle or u.last_vehicle,attendance_type=attendance_type,distance_from_office_m=office_distance,gps_accuracy_m=x.accuracy_m,verification_state='not_configured'));s.commit();return safe_user(u)
@app.get('/api/attendance')
def attendance(s:Session=Depends(db),_=Depends(manager)):
 return [{'id':a.id,'driver_id':a.driver_id,'kind':a.kind,'at':iso(a.at),'lat':a.lat,'lng':a.lng,'vehicle':a.vehicle,'attendance_type':a.attendance_type,'distance_from_office_m':a.distance_from_office_m,'gps_accuracy_m':a.gps_accuracy_m,'verification_state':a.verification_state} for a in s.scalars(select(Attendance).order_by(Attendance.at.desc()).limit(300))]
@app.post('/api/tasks')
async def create_task(x:TaskCreate,s:Session=Depends(db),_=Depends(manager)):
 u=s.get(User,x.driver_id)
 if not u or u.role!='driver':err(404,'Driver not found')
 if not u.approved or not u.license_verified or u.active is False:err(409,'Driver must be active with manager-verified licence before assignment')
 recipient_phone(x.customer_phone)
 if not -90<=x.lat<=90 or not -180<=x.lng<=180:err(400,'Invalid destination coordinates')
 t=Task(id=str(uuid.uuid4()),title=x.title,driver_id=x.driver_id,address=x.address,lat=x.lat,lng=x.lng,due_at=x.due_at,priority=x.priority,customer=x.customer,customer_phone=x.customer_phone,instructions=x.instructions,assigned_at=now())
 if u.lat is not None and u.lng is not None:
  r=await route_options(u.lat,u.lng,x.lat,x.lng);t.route_distance_km=r['distance_km'];t.route_duration_min=r['duration_min'];t.route_source=r['source'];import json;t.route_json=json.dumps(r['coordinates']);t.route_alternatives_json=json.dumps([alt.get('coordinates',[]) for alt in r.get('alternative_routes',[])])
 s.add(t);s.commit();return task_json(t,s)
class BulkDeliveryRequest(BaseModel):
 deliveries:list[TaskCreate]=Field(min_length=1,max_length=100)

@app.post('/api/tasks/bulk-preview')
def bulk_delivery_preview(x:BulkDeliveryRequest,s:Session=Depends(db),_=Depends(manager)):
 rows=[]
 for idx,task in enumerate(x.deliveries,1):
  issues=[];d=s.get(User,task.driver_id)
  if not d or d.role!='driver' or not d.active or not d.approved or not d.license_verified:issues.append('Driver not eligible')
  if not task.title.strip() or not task.address.strip():issues.append('Title and destination required')
  if not -90<=task.lat<=90 or not -180<=task.lng<=180:issues.append('Invalid coordinates')
  if not re.fullmatch(r'(?:[6-9][0-9]{9}|91[6-9][0-9]{9}|\+91[6-9][0-9]{9})',task.customer_phone or ''):issues.append('Recipient phone invalid')
  rows.append({'row':idx,'valid':not issues,'errors':issues,'driver_id':task.driver_id,'title':task.title})
 return {'total':len(rows),'valid':sum(r['valid'] for r in rows),'invalid':sum(not r['valid'] for r in rows),'rows':rows}

@app.post('/api/tasks/bulk-commit',status_code=201)
def bulk_delivery_commit(x:BulkDeliveryRequest,s:Session=Depends(db),_=Depends(manager)):
 preview=bulk_delivery_preview(x,s,_)
 if preview['invalid']:err(422,'Batch contains invalid tasks; preview and correct every row')
 saved=[]
 for item in x.deliveries:
  t=Task(id=str(uuid.uuid4()),title=item.title.strip(),driver_id=item.driver_id,address=item.address.strip(),lat=item.lat,lng=item.lng,due_at=item.due_at,priority=item.priority,customer=item.customer,customer_phone=item.customer_phone,instructions=item.instructions,assigned_at=now(),status='assigned')
  s.add(t);saved.append(t.id)
 s.commit()
 return {'created':len(saved),'task_ids':saved,'status':'assigned','route_calculation':'on_demand'}

@app.post('/api/tasks/{tid}/late-reason')
def submit_late_reason(tid:str,x:LateReason,u=Depends(driver),s:Session=Depends(db)):
 t=s.get(Task,tid)
 if not t or t.driver_id!=u.id:err(404,'Task not found')
 if t.status=='cancelled':err(409,'Cancelled delivery')
 t.late_reason=x.reason.strip();t.late_reason_at=now()
 new_alert(s,'driver_delay_reason',u.id,f'{u.name} reported delay for {t.title}: {x.reason.strip()}',tid,severity='warning',lat=u.lat,lng=u.lng)
 s.commit();return task_json(t,s)

@app.get('/api/driver/notifications')
def driver_notifications(u=Depends(driver),s:Session=Depends(db)):
 current=now();today=current.astimezone(ZoneInfo(os.getenv('BUSINESS_TIMEZONE','Asia/Kolkata'))).date()
 items=[]
 try:
  hh,mm=map(int,u.shift_expected.split(':'))
  shift=datetime.combine(today,datetime.min.time(),tzinfo=ZoneInfo(os.getenv('BUSINESS_TIMEZONE','Asia/Kolkata'))).replace(hour=hh,minute=mm).astimezone(timezone.utc)
  until=(shift-current).total_seconds()/60
  if not (u.shift_start and naive(u.shift_start)>=naive(shift)):
   if 0<=until<=5:items.append({'id':'shift-upcoming-'+today.isoformat(),'type':'shift_reminder','title':'Punch-in in 5 minutes','message':f'Your shift starts at {u.shift_expected}','at':iso(shift)})
   if -1440<until<0:items.append({'id':'shift-missed-'+today.isoformat(),'type':'missed_login','title':'Missed punch-in','message':f'Your {u.shift_expected} shift has started. Punch in if you are working.','at':iso(current)})
 except Exception:pass
 for t in s.scalars(select(Task).where(Task.driver_id==u.id,Task.status.in_(['assigned','in_progress']))):
  if t.status=='assigned':items.append({'id':'assignment-'+t.id,'type':'task_assignment','title':'New task assigned','message':f'{t.title} • {t.address}','at':iso(t.assigned_at or current)})
  if t.due_at:
   minutes=(naive(t.due_at)-naive(current)).total_seconds()/60
   if -1440<minutes<=0:items.append({'id':'late-'+t.id,'type':'deadline_missed','title':'Delivery overdue','message':t.title,'at':iso(t.due_at),'task_id':t.id})
   elif minutes<=15:items.append({'id':'deadline-'+t.id,'type':'deadline_warning','title':'Delivery deadline approaching','message':f'{t.title} due in {max(1,int(minutes))} min','at':iso(t.due_at),'task_id':t.id})
   if t.status=='in_progress' and u.lat is not None and u.lng is not None:
    eta=haversine(u.lat,u.lng,t.lat,t.lng)/25*60
    if minutes>0 and eta>minutes:items.append({'id':'predicted-'+t.id,'type':'predicted_delay','title':'Delivery may be late','message':f'{t.title}: ETA exceeds remaining time','at':iso(current),'task_id':t.id})
 return items

@app.get('/api/tasks')
def tasks(s:Session=Depends(db),u=Depends(require)):
 q=select(Task).order_by(Task.assigned_at.desc())
 if u.role=='driver':q=q.where(Task.driver_id==u.id)
 return [task_json(t,s) for t in s.scalars(q)]
@app.post('/api/tasks/{tid}/start')
def start_task(tid:str,u=Depends(driver),s:Session=Depends(db)):
 t=s.get(Task,tid)
 if not t or t.driver_id!=u.id:err(404,'Task not found')
 if t.status!='assigned':err(409,'Task not in assigned state')
 if s.scalar(select(Task.id).where(Task.driver_id==u.id,Task.status=='in_progress',Task.id!=tid)):
  err(409,'Complete the current delivery before starting the next queued delivery')
 t.status='in_progress';t.started_at=now();s.commit();return task_json(t,s)
@app.get('/api/tasks/{tid}/route')
async def task_route(tid:str,mode:str='fastest',s:Session=Depends(db),u=Depends(require)):
 t=s.get(Task,tid)
 if not t or (u.role=='driver' and t.driver_id!=u.id):err(404,'Task not found')
 if u.role in ('manager','super_admin'): d=s.get(User,t.driver_id)
 else:d=u
 if not d or d.lat is None or d.lng is None:err(400,'Driver must send GPS location first')
 return await route_options(d.lat,d.lng,t.lat,t.lng,mode)
# A deviation needs repeated reliable readings; avoid flooding alerts on every GPS update.
# Existing tasks.route_deviation is persistent. In-memory confirmation counts reset on restart/scale-out.
_deviation_samples={}
DEVIATION_METRES=max(50,min(1000,int(os.getenv('ROUTE_DEVIATION_METRES','150'))))
DEVIATION_CONFIRMATIONS=max(2,min(8,int(os.getenv('ROUTE_DEVIATION_CONFIRMATIONS','3'))))

@app.post('/api/gps')
def gps(x:Coords,u=Depends(driver),s:Session=Depends(db)):
 if not (u.shift_start and (not u.shift_end or naive(u.shift_start)>naive(u.shift_end))):err(409,'GPS tracking allowed during active shifts only')
 recorded=now()
 if x.captured_at is not None:
  captured=x.captured_at if x.captured_at.tzinfo else x.captured_at.replace(tzinfo=timezone.utc)
  captured=captured.astimezone(timezone.utc)
  if captured>recorded+timedelta(minutes=2) or captured<recorded-timedelta(days=7):err(422,'GPS capture time outside accepted range')
 else:captured=recorded
 # Samples from a previous shift are not allowed to rewrite a current journey.
 if u.shift_start and naive(captured)<naive(u.shift_start)-timedelta(seconds=30):err(409,'GPS sample belongs to a previous shift')
 if x.sample_id:
  prior=s.scalar(select(GPS.id).where(GPS.driver_id==u.id,GPS.sample_id==x.sample_id))
  if prior:return {'ok':True,'duplicate':True,'time':iso(u.last_gps),'server_time':iso(recorded),'deviation_alerts':[]}
 # An inaccurate or delayed sample may be kept for diagnosis, but cannot shift the live position.
 high_quality=x.accuracy_m is None or x.accuracy_m<=120
 newer=not u.last_gps or naive(captured)>naive(u.last_gps)
 if newer and high_quality:
  u.lat=x.lat;u.lng=x.lng;u.last_gps=captured
  # Only newly captured points prove that this device is currently reporting.
  if (recorded-captured).total_seconds()<=90:
   u.last_gps_received_at=recorded
 s.add(GPS(id=str(uuid.uuid4()),sample_id=x.sample_id,driver_id=u.id,task_id=x.task_id,lat=x.lat,lng=x.lng,at=recorded,accuracy_m=x.accuracy_m,speed_mps=x.speed_mps,captured_at=captured))
 deviations=[]
 fresh=(recorded-captured).total_seconds()<90 and (recorded-captured).total_seconds()>-20
 accurate=x.accuracy_m is not None and x.accuracy_m<=60
 if fresh and accurate and newer:
  for t in s.scalars(select(Task).where(Task.driver_id==u.id,Task.status=='in_progress')):
   if not t.route_json or not (t.route_source or '').startswith(('OSRM','TomTom')):continue
   try:
    permitted=[json.loads(t.route_json)]+json.loads(t.route_alternatives_json or '[]')
    distance_m=1000*min(line_distance_km(x.lat,x.lng,path) for path in permitted if len(path)>1)
   except (ValueError,TypeError):continue
   key=(u.id,t.id)
   if distance_m>DEVIATION_METRES:
    _deviation_samples[key]=_deviation_samples.get(key,0)+1
    if _deviation_samples[key]>=DEVIATION_CONFIRMATIONS and not t.route_deviation:
     t.route_deviation=True
     new_alert(s,'route_deviation',u.id,f'{u.name} deviated {distance_m:.0f} m from the saved route (confirmed GPS)',t.id,lat=x.lat,lng=x.lng)
     deviations.append(t.id)
   else:
    _deviation_samples.pop(key,None)
    if t.route_deviation:
     t.route_deviation=False
     new_alert(s,'route_restored',u.id,f'{u.name} returned to the saved route',t.id,lat=x.lat,lng=x.lng)
 s.commit()
 return {'ok':True,'duplicate':False,'accepted_live':bool(newer and high_quality and (recorded-captured).total_seconds()<=90),'time':iso(u.last_gps),'server_time':iso(recorded),'deviation_alerts':deviations}

def gps_freshness(u, current):
 """Shift membership and device connectivity must never be conflated.

 A delayed offline upload is stored in history but cannot make a driver look live.
 """
 last=u.last_gps
 if last is None or u.lat is None or u.lng is None:
  return None,'no_gps'
 stamp=u.last_gps_received_at or last
 if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=timezone.utc)
 age=max(0,(current-stamp).total_seconds())
 return round(age),'fresh' if age<=45 else 'stale' if age<=150 else 'offline'

@app.get('/api/tracking/status')
def driver_tracking_status(u=Depends(driver),s:Session=Depends(db)):
 current=now()
 age,status=gps_freshness(u,current)
 active=bool(u.shift_start and (not u.shift_end or naive(u.shift_start)>naive(u.shift_end)))
 return {'driver_id':u.id,'on_shift':active,'last_gps':iso(u.last_gps),
         'last_gps_received_at':iso(u.last_gps_received_at),
         'gps_age_seconds':age,'gps_status':status,'server_time':iso(current)}

@app.get('/api/tracking/fleet')
def fleet_tracking(s:Session=Depends(db),_=Depends(manager)):
 current=now()
 drivers=list(s.scalars(select(User).where(User.role=='driver',User.active==True)))
 active_tasks={t.driver_id:t for t in s.scalars(select(Task).where(Task.status=='in_progress').order_by(Task.started_at.desc()))}
 result=[]
 for u in drivers:
  age,status=gps_freshness(u,current)
  photo_ok=bool(u.face_path and u.face_review_status=='approved')
  task=active_tasks.get(u.id)
  result.append({'driver_id':u.id,'name':u.name,'vehicle':u.vehicle,
   'on_shift':bool(u.shift_start and (not u.shift_end or naive(u.shift_start)>naive(u.shift_end))),
   'lat':u.lat,'lng':u.lng,'last_gps':iso(u.last_gps),
   'last_gps_received_at':iso(u.last_gps_received_at),
   'gps_age_seconds':age,'gps_status':status,
   'approved_photo_url':('/api/files/'+Path(u.face_path).name) if photo_ok else None,
   'current_task':task_json(task,s) if task else None})
 return {'server_time':iso(current),'drivers':result}

@app.get('/api/gps/{driver_id}')
def gps_history(driver_id:str,s:Session=Depends(db),_=Depends(manager)):
 records=list(s.scalars(select(GPS).where(GPS.driver_id==driver_id).order_by(GPS.captured_at.desc(),GPS.at.desc()).limit(300)))
 return [{'lat':p.lat,'lng':p.lng,'at':iso(p.captured_at or p.at),'received_at':iso(p.at),'accuracy_m':p.accuracy_m,'speed_mps':p.speed_mps,'task_id':p.task_id} for p in records]

def recipient_phone(value):
 digits=re.sub(r'[^0-9]','',value or '')
 if len(digits)==10 and digits[0] in '6789':return '+91'+digits
 if len(digits)==12 and digits.startswith('91') and digits[2] in '6789':return '+'+digits
 if value and value.startswith('+') and 10<=len(digits)<=15:return '+'+digits
 err(422,'Valid customer mobile number required for OTP delivery')

@app.post('/api/tasks/{tid}/otp/send')
async def send_customer_otp(tid:str,s:Session=Depends(db),u=Depends(driver)):
 t=s.get(Task,tid)
 if not t or t.driver_id!=u.id:err(404,'Task not found')
 if t.status!='in_progress':err(409,'Start the task before requesting the customer OTP')
 phone=recipient_phone(t.customer_phone)
 sid=os.getenv('TWILIO_ACCOUNT_SID','').strip();secret=os.getenv('TWILIO_AUTH_TOKEN','').strip();sender=os.getenv('TWILIO_FROM_NUMBER','').strip()
 if not (sid and secret and sender):err(503,'Customer SMS is not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN and TWILIO_FROM_NUMBER. No OTP was issued.')
 # Simple database-backed cooldown: prevents rapid SMS retries on same active task.
 if t.otp_expires and naive(t.otp_expires)>naive(now()+timedelta(minutes=9)):err(429,'Please wait at least one minute before requesting another OTP')
 code=f'{secrets.randbelow(1000000):06d}'
 try:
  async with httpx.AsyncClient(timeout=12) as client:
   response=await client.post(f'https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json',auth=(sid,secret),data={'To':phone,'From':sender,'Body':f'KRIYA360 delivery {t.title}: your confirmation code is {code}. Share it only after receiving the delivery. Expires in 10 minutes.'})
  response.raise_for_status()
  delivery_id=response.json().get('sid','')
  if not delivery_id:err(502,'SMS provider did not confirm acceptance; no OTP issued')
 except httpx.HTTPError:err(502,'SMS provider could not accept the message; no OTP issued')
 t.otp_hash=hash_pin(code);t.otp_expires=now()+timedelta(minutes=10);t.otp_attempts=0;s.commit()
 return {'status':'accepted_by_sms_provider','recipient_masked':'******'+phone[-4:],'expires_at':iso(t.otp_expires),'message_id':delivery_id,'notice':'SMS provider acceptance does not guarantee handset delivery'}

@app.post('/api/tasks/{tid}/otp/generate')
def old_manager_otp_disabled(tid:str,s:Session=Depends(db),_=Depends(manager)):
 err(410,'Management OTP generation has been disabled; the assigned driver requests recipient SMS through /otp/send')

@app.post('/api/tasks/{tid}/complete')
async def complete_task(tid:str,otp:str=Form(...),image:UploadFile=File(...),u=Depends(driver),s:Session=Depends(db)):
 t=s.get(Task,tid)
 if not t or t.driver_id!=u.id:err(404,'Task not found')
 if t.status!='in_progress':err(409,'Start delivery before completion')
 if (t.otp_attempts or 0)>=5:err(429,'Too many invalid OTP attempts; request another code after expiry')
 if not t.otp_hash or not t.otp_expires or naive(t.otp_expires)<naive(now()):err(400,'OTP not issued or expired')
 if not check_pin(otp,t.otp_hash):
  t.otp_attempts=(t.otp_attempts or 0)+1;s.commit();err(400,'OTP invalid or expired')
 path=await store_image(image);t.proof_path=str(path);t.status='completed';t.completed_at=now();t.otp_verified=True;t.otp_hash='';s.commit();return task_json(t,s)
async def store_image(upload:UploadFile):
 data=await upload.read(5*1024*1024+1)
 if len(data)>5*1024*1024:err(413,'Image too large; max 5 MB')
 from PIL import Image
 from io import BytesIO
 try:
  im=Image.open(BytesIO(data));im.verify()
  im=Image.open(BytesIO(data)).convert('RGB');im.thumbnail((1600,1600))
 except Exception:err(415,'Valid image required')
 path=UPLOAD/(str(uuid.uuid4())+'.jpg');im.save(path,'JPEG',quality=85);return path
@app.get('/api/files/{filename}')
def private_file(filename:str,u=Depends(require),s:Session=Depends(db)):
 # Require authentication, restrict by ownership (driver) or manager role.
 if filename!=Path(filename).name:err(400,'Invalid filename')
 path=UPLOAD/filename
 if not path.exists():err(404,'File not found')
 if u.role in ('manager','super_admin'):
  candidate=s.scalar(select(User).where(User.role=='driver',User.license_path==str(path)))
  if candidate:candidate.license_inspected_at=now();candidate.license_inspected_by=u.id;s.commit()
 if u.role not in ('manager','super_admin'):
  allowed=bool(u.face_path and Path(u.face_path).name==filename)
  allowed|=bool(u.license_path and Path(u.license_path).name==filename)
  allowed|=bool(s.scalar(select(Task).where(Task.driver_id==u.id,Task.proof_path==str(path))))
  allowed|=bool(s.scalar(select(Expense).where(Expense.driver_id==u.id,Expense.receipt_path==str(path))))
  if not allowed:err(403,'Forbidden')
 return FileResponse(path)
@app.post('/api/expenses/submit-evidence')
async def submit_evidence_expense(task_id:str=Form(...),category:str=Form(...),amount:float=Form(...),image:UploadFile=File(...),u=Depends(driver),s:Session=Depends(db)):
 t=s.get(Task,task_id)
 if not t or t.driver_id!=u.id:err(404,'Assigned delivery not found')
 if category not in ('fuel','toll','parking','food','other'):err(400,'Invalid expense category')
 if not (0<amount<=1000000):err(400,'Invalid expense amount')
 path=await store_image(image)
 raw=path.read_bytes();sha=hashlib.sha256(raw).hexdigest()
 from PIL import Image
 import json
 with Image.open(path) as im:
  gray=im.convert('L').resize((9,8))
  px=list(gray.getdata())
  visual=''.join('1' if px[y*9+x]>px[y*9+x+1] else '0' for y in range(8) for x in range(8))
 flags=[]
 if s.scalar(select(Expense).where(Expense.evidence_sha==sha)):flags.append('Duplicate payment image submitted previously')
 prior=s.scalars(select(Expense).where(Expense.evidence_visual.is_not(None),Expense.evidence_visual!='')).all()
 if any(sum(a!=b for a,b in zip(visual,old.evidence_visual or ''))<=4 for old in prior if len(old.evidence_visual or '')==64):flags.append('Visually similar receipt to a prior submission')
 if amount>25000:flags.append('Unusually high expense amount; needs manual verification')
 # OCR and forgery classifier are deliberately NOT claimed without a validated model.
 e=Expense(id=str(uuid.uuid4()),driver_id=u.id,task_id=task_id,category=category,amount=amount,created_at=now(),receipt_path=str(path),evidence_sha=sha,evidence_visual=visual,fraud_flags=json.dumps(flags),evidence_reviewed=False,status='pending')
 s.add(e)
 if flags:new_alert(s,'expense_review',u.id,f'Expense ₹{amount:.2f} flagged for review: {"; ".join(flags)}',task_id,severity='warning')
 s.commit();return expense_json(e,s)

@app.post('/api/expenses/{eid}/mark-reviewed')
def mark_expense_reviewed(eid:str,s:Session=Depends(db),_=Depends(manager)):
 e=s.get(Expense,eid)
 if not e:err(404,'Expense not found')
 if not e.receipt_path:err(409,'No payment evidence uploaded')
 e.evidence_reviewed=True;e.reviewed_at=now();s.commit();return expense_json(e,s)

@app.post('/api/expenses')
def add_expense(x:ExpenseCreate,u=Depends(driver),s:Session=Depends(db)):
 t=s.get(Task,x.task_id)
 if not t or t.driver_id!=u.id:err(404,'Task not found')
 if x.category not in ('fuel','toll','parking','food','other'):err(400,'Invalid expense category')
 e=Expense(id=str(uuid.uuid4()),driver_id=u.id,task_id=x.task_id,category=x.category,amount=x.amount,note=x.note,created_at=now());s.add(e);s.commit();return expense_json(e,s)
@app.post('/api/expenses/{eid}/receipt')
async def receipt(eid:str,image:UploadFile=File(...),u=Depends(driver),s:Session=Depends(db)):
 e=s.get(Expense,eid)
 if not e or e.driver_id!=u.id:err(404,'Expense not found')
 e.receipt_path=str(await store_image(image));s.commit();return expense_json(e,s)
@app.get('/api/expenses')
def expenses(s:Session=Depends(db),u=Depends(require)):
 q=select(Expense).order_by(Expense.created_at.desc())
 if u.role=='driver':q=q.where(Expense.driver_id==u.id)
 return [expense_json(e,s) for e in s.scalars(q)]
@app.patch('/api/expenses/{eid}')
def approve_expense(eid:str,x:StatusUpdate,s:Session=Depends(db),_=Depends(manager)):
 e=s.get(Expense,eid)
 if not e:err(404,'Expense not found')
 if x.status not in ('approved','rejected'):err(400,'Invalid status')
 if not e.receipt_path or not e.evidence_reviewed:err(409,'Review uploaded payment evidence before deciding')
 e.status=x.status;s.commit();return expense_json(e,s)
@app.post('/api/sos')
def sos(x:SOSCreate,u=Depends(driver),s:Session=Depends(db)):
 if not x.confirmed:err(400,'Driver confirmation required')
 a=Alert(id=str(uuid.uuid4()),kind='sos',driver_id=u.id,message=x.message[:400],severity='critical',at=now(),lat=x.lat if x.lat is not None else u.lat,lng=x.lng if x.lng is not None else u.lng,status='open')
 s.add(a);s.commit();return {'id':a.id,'status':'received_by_server','at':iso(a.at)}
@app.get('/api/alerts')
def alerts(s:Session=Depends(db),_=Depends(manager)):
 update_alerts(s)
 return [alert_json(a,s) for a in s.scalars(select(Alert).order_by(Alert.at.desc()).limit(200))]
@app.patch('/api/alerts/{aid}')
def resolve_alert(aid:str,x:StatusUpdate,s:Session=Depends(db),_=Depends(manager)):
 a=s.get(Alert,aid)
 if not a:err(404,'Alert not found')
 if x.status not in ('acknowledged','resolved'):err(400,'Invalid status')
 if a.status=='resolved' or (a.status=='acknowledged' and x.status=='acknowledged'):err(409,'Incident already handled')
 a.status=x.status;s.commit();return alert_json(a,s)

def update_alerts(s):
 current=naive(now());local_now=now().astimezone(ZoneInfo(os.getenv("BUSINESS_TIMEZONE","Asia/Kolkata")));today=local_now.date()
 for t in s.scalars(select(Task).where(Task.status!='completed',Task.status!='cancelled')):
  if t.due_at and naive(t.due_at)<current:
   new_alert(s,'late_delivery',t.driver_id,f'Delivery {t.title} is overdue',t.id)
  elif t.due_at and t.status=='in_progress':
   d=s.get(User,t.driver_id)
   if d and d.lat is not None:
    remain=haversine(d.lat,d.lng,t.lat,t.lng)/25*60
    if naive(t.due_at)<current+timedelta(minutes=remain):new_alert(s,'predicted_delay',t.driver_id,f'Delivery {t.title} may miss its deadline',t.id)
 for d in s.scalars(select(User).where(User.role=='driver')):
  try:hh,mm=map(int,d.shift_expected.split(':'))
  except Exception:continue
  # Uses server timezone; set TZ for operating location in deployment.
  threshold=datetime.combine(today,datetime.min.time(),tzinfo=ZoneInfo(os.getenv("BUSINESS_TIMEZONE","Asia/Kolkata"))).replace(hour=hh,minute=mm).astimezone(timezone.utc).replace(tzinfo=None)+timedelta(minutes=15)
  if current>threshold and not (d.shift_start and d.shift_start.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(os.getenv("BUSINESS_TIMEZONE","Asia/Kolkata"))).date()==today):
   new_alert(s,'missed_punch_in',d.id,f'{d.name} missed scheduled punch-in at {d.shift_expected}')
 s.commit()

# Limited-use OSM geocoding: search only on explicit manager action; cache searches to
# keep requests low. For production use a contracted geocoding provider.
_geocode_cache={}
_geocode_last_at=0.0
# Resolve display names without exposing location-service credentials to browsers.
# Only reverse geocode explicitly selected fleet positions (not every poll).
_reverse_names_cache={}
@app.get('/api/geocode/reverse')
async def reverse_geocode(lat:float,lng:float,_=Depends(manager)):
 if not (-90<=lat<=90 and -180<=lng<=180) or not (math.isfinite(lat) and math.isfinite(lng)):
  err(422,'Invalid coordinates')
 key=os.getenv('GEOAPIFY_API_KEY','').strip()
 if not key:return {'name':None,'available':False}
 cache_key=(round(lat,4),round(lng,4))
 current=time.time()
 cached=_reverse_names_cache.get(cache_key)
 if cached and current-cached[0]<3600:return {'name':cached[1],'available':bool(cached[1])}
 try:
  async with httpx.AsyncClient(timeout=8.0) as client:
   resp=await client.get('https://api.geoapify.com/v1/geocode/reverse',params={'lat':lat,'lon':lng,'apiKey':key,'format':'json','limit':1})
   resp.raise_for_status()
   results=resp.json().get('results') or []
   row=results[0] if results else {}
   name=(row.get('formatted') or row.get('address_line1') or row.get('city') or '').strip() or None
   if len(_reverse_names_cache)>1000:_reverse_names_cache.clear()
   _reverse_names_cache[cache_key]=(current,name)
   return {'name':name,'available':bool(name)}
 except (httpx.HTTPError,ValueError):
  return {'name':None,'available':False}

@app.get('/api/geocode/search')
async def geocode_search(q:str, _=Depends(manager)):
 global _geocode_last_at
 q=q.strip()
 if len(q)<3 or len(q)>150:err(422,'Enter a location of 3-150 characters')
 cache_key=q.casefold()
 if cache_key in _geocode_cache:return {'results':_geocode_cache[cache_key]}
 if time.monotonic()-_geocode_last_at<0.4:err(429,'Search rate limit: try again shortly')
 _geocode_last_at=time.monotonic()
 api_key=os.getenv('GEOAPIFY_API_KEY','').strip()
 results=[];errors=[];seen=set()
 try:
  async with httpx.AsyncClient(timeout=12) as client:
   if api_key:
    # Geocoding + autocomplete. POI/building coverage is dependent on provider indexing.
    for endpoint,params in [
     ('https://api.geoapify.com/v1/geocode/search',{'text':q,'limit':10,'format':'json','apiKey':api_key}),
     ('https://api.geoapify.com/v1/geocode/autocomplete',{'text':q,'limit':10,'format':'json','apiKey':api_key}),
    ]:
     try:
      response=await client.get(endpoint,params=params);response.raise_for_status()
      for item in response.json().get('results',[]):
       if item.get('lat') is None or item.get('lon') is None:continue
       lat,lng=float(item['lat']),float(item['lon'])
       label=str(item.get('formatted') or item.get('name') or item.get('address_line1') or '').strip()[:240]
       ident=(round(lat,5),round(lng,5),label.lower())
       if not label or ident in seen:continue
       seen.add(ident);results.append({'label':label,'lat':lat,'lng':lng,'type':item.get('result_type','place')})
     except (httpx.HTTPError,ValueError,KeyError) as e:errors.append(type(e).__name__)
   if not api_key:
    response=await client.get('https://nominatim.openstreetmap.org/search',params={'q':q,'format':'jsonv2','limit':10},headers={'User-Agent':'KRIYA360/1.0 (operations search)'})
    response.raise_for_status()
    results=[{'label':str(v.get('display_name',''))[:240],'lat':float(v['lat']),'lng':float(v['lon'])} for v in response.json() if v.get('lat') and v.get('lon')]
 except (httpx.HTTPError,ValueError,KeyError):err(503,'Search provider temporarily unavailable; pin the destination manually')
 if errors and not results:err(503,'Geoapify search unsuccessful; check key, API access and backend logs')
 if len(_geocode_cache)>150:_geocode_cache.clear()
 _geocode_cache[cache_key]=results[:15]
 return {'results':results[:15]}

class ManagerAccountCreate(BaseModel):
 name:str=Field(min_length=2,max_length=120)
 phone:str
 email:str
 password:str
class ManagerAccountPatch(BaseModel):
 name:Optional[str]=Field(default=None,min_length=2,max_length=120)
 phone:Optional[str]=None
 email:Optional[str]=None
 password:Optional[str]=None
def safe_manager(u):return {'id':u.id,'name':u.name,'phone':u.phone,'email':u.email or '', 'active':u.active is not False,'role':u.role}
@app.get('/api/management/users')
def management_users(s:Session=Depends(db),_=Depends(super_admin)):
 return [safe_manager(u) for u in s.scalars(select(User).where(User.role.in_(['manager','super_admin'])).order_by(User.name)).all()]
@app.post('/api/management/users')
def create_management_user(x:ManagerAccountCreate,s:Session=Depends(db),_=Depends(super_admin)):
 check_phone(x.phone)
 if s.scalar(select(User).where(User.phone==x.phone)):err(409,'Phone is already in use')
 email=normalized_email(x.email);valid_password(x.password)
 if s.scalar(select(User).where(User.email==email)):err(409,'Email already in use')
 u=User(id=str(uuid.uuid4()),role='manager',name=x.name.strip(),phone=x.phone,email=email,password_hash=hash_pin(x.password),pin_hash=hash_pin(secrets.token_urlsafe(32)),approved=True,active=True)
 s.add(u);s.commit();return safe_manager(u)
@app.patch('/api/management/users/{uid}')
def edit_management_user(uid:str,x:ManagerAccountPatch,s:Session=Depends(db),_=Depends(super_admin)):
 u=s.get(User,uid)
 if not u or u.role not in ('manager','super_admin'):err(404,'Management account not found')
 if x.name is not None:u.name=x.name.strip()
 if x.phone is not None:
  check_phone(x.phone)
  conflict=s.scalar(select(User).where(User.phone==x.phone,User.id!=uid))
  if conflict:err(409,'Phone is already in use')
  u.phone=x.phone
 if x.email is not None:
  email=normalized_email(x.email)
  if s.scalar(select(User).where(User.email==email,User.id!=uid)):err(409,'Email already in use')
  u.email=email
 if x.password:
  valid_password(x.password);u.password_hash=hash_pin(x.password)
 s.commit();return safe_manager(u)
@app.delete('/api/management/users/{uid}')
def deactivate_management_user(uid:str,s:Session=Depends(db),current=Depends(super_admin)):
 u=s.get(User,uid)
 if not u or u.role not in ('manager','super_admin'):err(404,'Management account not found')
 if u.id==current.id or u.role=='super_admin':err(409,'Super admin cannot be deactivated through manager maintenance')
 u.active=False;s.commit();return {'ok':True,'id':uid}

@app.get('/api/overview')
def overview(s:Session=Depends(db),_=Depends(manager)):
 update_alerts(s)
 ds=s.scalars(select(User).where(User.role=='driver')).all();ts=s.scalars(select(Task)).all();es=s.scalars(select(Expense)).all();al=s.scalars(select(Alert).where(Alert.status=='open')).all()
 total=sum(e.amount for e in es if e.status=='approved');pending=sum(e.amount for e in es if e.status=='pending')
 return {'drivers':len(ds),'active_drivers':sum(bool(d.shift_start and (not d.shift_end or naive(d.shift_start)>naive(d.shift_end))) for d in ds),'total_tasks':len(ts),'in_progress':sum(t.status=='in_progress' for t in ts),'completed':sum(t.status=='completed' for t in ts),'delayed':sum(bool(t.due_at and naive(t.due_at)<naive(now()) and t.status!='completed') for t in ts),'approved_expenses':round(total,2),'pending_expenses':round(pending,2),'open_alerts':len(al),'critical_alerts':sum(a.severity=='critical' for a in al)}
@app.get('/api/performance')
def performance(s:Session=Depends(db),_=Depends(manager)):
 result=[]
 for d in s.scalars(select(User).where(User.role=='driver')):
  ts=s.scalars(select(Task).where(Task.driver_id==d.id)).all();done=[t for t in ts if t.status=='completed'];approved=s.scalars(select(Expense).where(Expense.driver_id==d.id,Expense.status=='approved')).all()
  timely=sum(bool(t.due_at and t.completed_at and naive(t.completed_at)<=naive(t.due_at)) for t in done)
  result.append({'driver_id':d.id,'name':d.name,'total':len(ts),'completed':len(done),'on_time':timely,'on_time_rate':round(100*timely/len(done)) if done else None,'late_deliveries':sum(bool(t.due_at and t.completed_at and naive(t.completed_at)>naive(t.due_at)) for t in done),'avg_delay_min':round(sum(max(0,(naive(t.completed_at)-naive(t.due_at)).total_seconds()/60) for t in done if t.due_at and t.completed_at)/sum(bool(t.due_at and t.completed_at and naive(t.completed_at)>naive(t.due_at)) for t in done),1) if any(t.due_at and t.completed_at and naive(t.completed_at)>naive(t.due_at) for t in done) else None,'approved_expenses':round(sum(e.amount for e in approved),2)})
 return result
@app.get('/api/driver-suggestions')
def suggestions(lat:float,lng:float,s:Session=Depends(db),_=Depends(manager)):
 if not (-90<=lat<=90 and -180<=lng<=180):err(400,'Invalid destination')
 items=[]
 for d in s.scalars(select(User).where(User.role=='driver',User.approved==True)):
  active=bool(d.shift_start and (not d.shift_end or naive(d.shift_start)>naive(d.shift_end)))
  distance=haversine(d.lat,d.lng,lat,lng) if d.lat is not None and d.lng is not None else None
  load=s.scalar(select(func.count()).select_from(Task).where(Task.driver_id==d.id,Task.status.in_(['assigned','in_progress']))) or 0
  score=(distance if distance is not None else 1000)+load*8+(0 if active else 100)
  items.append({'driver_id':d.id,'name':d.name,'distance_km':round(distance,1) if distance is not None else None,'active':active,'active_tasks':load,'score':round(score,2),'method':'transparent heuristic; not trained ML'})
 return sorted(items,key=lambda x:x['score'])

if DEMO:
  # Seed only when neither the fixed demo ID nor its phone is already used.
  # Existing records may have been edited through manager CRUD; never overwrite them.
  with SessionLocal() as s:
   manager_by_id=s.get(User,'manager-demo')
   manager_by_phone=s.scalar(select(User).where(User.phone=='9000000000'))
   if manager_by_id is None and manager_by_phone is None:
    s.add(User(id='manager-demo',role='manager',name='Operations Manager',phone='9000000000',pin_hash=hash_pin('1234')))
   driver_by_id=s.get(User,'driver-demo')
   driver_by_phone=s.scalar(select(User).where(User.phone=='9000000001'))
   if driver_by_id is None and driver_by_phone is None:
    s.add(User(id='driver-demo',role='driver',name='Arjun Kumar',phone='9000000001',pin_hash=hash_pin('1234'),license_no='DEMO-LICENCE',vehicle='Truck',vehicle_plate='KA-01-DEMO',lat=12.9716,lng=77.5946,last_gps=now(),shift_expected='09:00',approved=True,license_verified=True))
   s.commit()
   demo_driver=s.scalar(select(User).where(User.phone=='9000000001'))
   if demo_driver and demo_driver.vehicle=='Two Wheeler':
    demo_driver.vehicle='Truck'
    s.commit()

# --- Reporting and bulk-driver onboarding (additive endpoints) ---
DL_PATTERN=re.compile(r'^[A-Z]{2}[0-9]{2}(?:19|20)[0-9]{2}[0-9]{7}$')
PHONE_PATTERN=re.compile(r'^[6-9][0-9]{9}$')

def pin_change_actor(authorization:Optional[str]=Header(None),s:Session=Depends(db)):
 if not authorization or not authorization.startswith('Bearer '):err(401,'Login required')
 try:body=jwt.decode(authorization[7:],JWT_SECRET,algorithms=['HS256'])
 except Exception:err(401,'Invalid token')
 u=s.get(User,body.get('sub'))
 if not u or u.active is False:err(403,'Account unavailable')
 return u

class PasswordChange(BaseModel):
 old_pin:str=Field(min_length=4,max_length=64)
 new_pin:str=Field(min_length=6,max_length=64)

@app.post('/api/me/change-pin')
def change_pin(x:PasswordChange,u=Depends(pin_change_actor),s:Session=Depends(db)):
 if not check_pin(x.old_pin,u.pin_hash):err(403,'Current PIN is incorrect')
 if x.new_pin==x.old_pin:err(422,'New PIN must differ')
 u.pin_hash=hash_pin(x.new_pin);u.pin_change_required=False;s.commit()
 return {'ok':True,'pin_change_required':False}

def _local_day(timestamp,tz):
 if not timestamp:return None
 return timestamp.replace(tzinfo=timezone.utc).astimezone(tz).date() if timestamp.tzinfo is None else timestamp.astimezone(tz).date()

def _attendance_report_rows(s,driver_id=None,start=None,end=None):
 tz=ZoneInfo(os.getenv('BUSINESS_TIMEZONE','Asia/Kolkata'))
 events=s.scalars(select(Attendance).order_by(Attendance.at.asc())).all()
 users={u.id:u for u in s.scalars(select(User).where(User.role=='driver'))}
 groups={};out=[]
 for e in events:
  if driver_id and e.driver_id!=driver_id:continue
  day=_local_day(e.at,tz)
  if start and day<datetime.strptime(start,'%Y-%m-%d').date():continue
  if end and day>datetime.strptime(end,'%Y-%m-%d').date():continue
  key=(e.driver_id,str(day))
  if e.kind=='in':
   # Keep distinct shifts in the same day, including subsequent check-ins.
   row={'driver_id':e.driver_id,'driver':users[e.driver_id].name if e.driver_id in users else 'Unknown driver','date':str(day),'punch_in':iso(e.at),'punch_out':None,'in_lat':e.lat,'in_lng':e.lng,'out_lat':None,'out_lng':None,'shift_expected':users[e.driver_id].shift_expected if e.driver_id in users else '09:00'}
   groups.setdefault(key,[]).append(row);out.append(row)
  else:
   prior=groups.get(key,[])
   pending=next((r for r in reversed(prior) if not r['punch_out']),None)
   if pending:pending.update(punch_out=iso(e.at),out_lat=e.lat,out_lng=e.lng)
   else:
    row={'driver_id':e.driver_id,'driver':users[e.driver_id].name if e.driver_id in users else 'Unknown driver','date':str(day),'punch_in':None,'punch_out':iso(e.at),'in_lat':None,'in_lng':None,'out_lat':e.lat,'out_lng':e.lng,'shift_expected':users[e.driver_id].shift_expected if e.driver_id in users else '09:00'};out.append(row)
 for row in out:
  try:
   hh,mm=map(int,row['shift_expected'].split(':'))
   expected=datetime.fromisoformat(row['date']).replace(hour=hh,minute=mm,tzinfo=tz)
   actual=datetime.fromisoformat(row['punch_in'].replace('Z','+00:00')).astimezone(tz) if row['punch_in'] else None
   # 15-minute grace; configurable per installation.
   row['late_minutes']=max(0,round((actual-expected).total_seconds()/60)) if actual and actual>expected+timedelta(minutes=int(os.getenv('ATTENDANCE_GRACE_MIN','15'))) else 0
  except Exception:row['late_minutes']=None
  row['status']='Unmatched punch-out' if not row['punch_in'] else ('Late' if row['late_minutes'] else 'On time') if row['punch_out'] else ('Late / on duty' if row['late_minutes'] else 'On duty')
  row['worked_minutes']=round((datetime.fromisoformat(row['punch_out'].replace('Z','+00:00'))-datetime.fromisoformat(row['punch_in'].replace('Z','+00:00'))).total_seconds()/60) if row['punch_in'] and row['punch_out'] else None
 return sorted(out,key=lambda r:r['punch_in'] or r['punch_out'] or '',reverse=True)

@app.get('/api/reports/attendance')
def attendance_report(driver_id:Optional[str]=None,start:Optional[str]=None,end:Optional[str]=None,s:Session=Depends(db),_=Depends(manager)):
 for val in (start,end):
  if val:
   try:datetime.strptime(val,'%Y-%m-%d')
   except ValueError:err(422,'Date format must be YYYY-MM-DD')
 rows=_attendance_report_rows(s,driver_id,start,end)
 drivers=[d for d in s.scalars(select(User).where(User.role=='driver')) if not driver_id or d.id==driver_id]
 summaries=[]
 for d in drivers:
  records=[r for r in rows if r['driver_id']==d.id]
  days={r['date'] for r in records if r['punch_in']}
  late=sum(r['late_minutes'] is not None and r['late_minutes']>0 for r in records)
  summaries.append({'driver_id':d.id,'name':d.name,'punch_ins':sum(bool(r['punch_in']) for r in records),'late_punch_ins':late,'on_time_punch_ins':sum(bool(r['punch_in']) and r['late_minutes']==0 for r in records),'completed_shifts':sum(bool(r['punch_out'] and r['punch_in']) for r in records),'days_observed':len(days),'on_time_percent':round(100*sum(bool(r['punch_in']) and r['late_minutes']==0 for r in records)/max(1,sum(bool(r['punch_in']) for r in records)),1) if any(r['punch_in'] for r in records) else None,'missed_punch_ins':sum(a.kind=='missed_punch_in' and a.driver_id==d.id and (not start or str(_local_day(a.at,tz))>=start) and (not end or str(_local_day(a.at,tz))<=end) for a in s.scalars(select(Alert).where(Alert.driver_id==d.id)).all())})
 return {'records':rows,'drivers':summaries,'grace_minutes':int(os.getenv('ATTENDANCE_GRACE_MIN','15')),'notes':'Missed punch-ins are counted only when KRIYA360 generated a recorded missed-punch alert. A duty roster and leave calendar are needed for complete absence accounting.'}

@app.get('/api/reports/attendance.csv')
def attendance_csv(driver_id:Optional[str]=None,start:Optional[str]=None,end:Optional[str]=None,s:Session=Depends(db),_=Depends(manager)):
 rows=attendance_report(driver_id,start,end,s)
 f=io.StringIO();cols=['driver','date','shift_expected','punch_in','punch_out','late_minutes','worked_minutes','status','in_lat','in_lng','out_lat','out_lng'];w=csv.writer(f);w.writerow(cols)
 for row in rows['records']:w.writerow([row.get(k,'') for k in cols])
 return Response(content='\ufeff'+f.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="KRIYA360_attendance.csv"'})

@app.get('/api/drivers/import-template.csv')
def import_template(_=Depends(manager)):
 return Response(content='full_name,phone,license_number,vehicle_type,vehicle_number,shift_start,shift_end\n',media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="KRIYA360_drivers_template.csv"'})

def _validate_import(raw,s):
 if len(raw)>1024*1024:err(413,'Maximum CSV size is 1 MB')
 try:content=raw.decode('utf-8-sig')
 except UnicodeDecodeError:err(422,'CSV must use UTF-8')
 reader=csv.DictReader(io.StringIO(content))
 required={'full_name','phone','license_number','shift_start','shift_end'}
 if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):err(422,'Missing CSV columns: '+', '.join(sorted(required-set(reader.fieldnames or []))))
 rows=list(reader)
 if not rows or len(rows)>500:err(422,'Upload between 1 and 500 driver records')
 existing_phones=set(s.scalars(select(User.phone)).all());seen=set();results=[]
 for i,row in enumerate(rows,2):
  name=(row.get('full_name') or '').strip();phone=(row.get('phone') or '').strip();license=(row.get('license_number') or '').strip().upper().replace(' ','');shift=(row.get('shift_start') or '').strip();end=(row.get('shift_end') or '').strip();vehicle=(row.get('vehicle_type') or '').strip();plate=(row.get('vehicle_number') or '').strip()
  errors=[]
  if not 2<=len(name)<=120 or name[0] in '=+@-\t':errors.append('Invalid full name')
  if not PHONE_PATTERN.fullmatch(phone):errors.append('Phone must be 10-digit Indian mobile')
  if phone in seen or phone in existing_phones:errors.append('Duplicate phone number')
  seen.add(phone)
  if not DL_PATTERN.fullmatch(license):errors.append('Invalid driving licence format')
  for value,label in [(shift,'Shift start'),(end,'Shift end')]:
   try:datetime.strptime(value,'%H:%M')
   except ValueError:errors.append(label+' must be HH:MM')
  if vehicle and vehicle not in {'Truck','Lorry','Heavy Truck','Container Truck'}:errors.append('Unsupported vehicle type')
  results.append({'row':i,'name':name,'phone':phone,'license_no':license,'vehicle':vehicle,'vehicle_plate':plate,'shift_expected':shift,'shift_end':end,'errors':errors,'valid':not errors})
 return results

@app.post('/api/drivers/import-preview')
async def import_preview(file:UploadFile=File(...),s:Session=Depends(db),_=Depends(manager)):
 rows=_validate_import(await file.read(),s)
 return {'total':len(rows),'valid':sum(r['valid'] for r in rows),'invalid':sum(not r['valid'] for r in rows),'rows':rows}

@app.post('/api/drivers/import-commit')
async def import_commit(file:UploadFile=File(...),s:Session=Depends(db),_=Depends(manager)):
 rows=_validate_import(await file.read(),s)
 if any(not r['valid'] for r in rows):err(422,'CSV contains invalid or duplicate rows. Correct the preview errors before importing; no accounts created.')
 created=[]
 for row in rows:
  pin=''.join(str(secrets.randbelow(10)) for _ in range(8))
  u=User(id=str(uuid.uuid4()),role='driver',name=row['name'],phone=row['phone'],pin_hash=hash_pin(pin),pin_change_required=True,license_no=row['license_no'],vehicle=row['vehicle'],vehicle_plate=row['vehicle_plate'],shift_expected=row['shift_expected'],shift_end_expected=row['shift_end'],approved=False,license_verified=False,active=True)
  s.add(u);created.append({'name':row['name'],'phone':row['phone'],'temporary_pin':pin,'status':'Pending document review'})
 s.commit()
 return {'created':len(created),'credentials_once':created,'warning':'Temporary PINs appear only in this response. Download them securely and ask drivers to change PIN at first sign-in.'}

@app.get('/api/routing/emergency')
async def emergency_route(from_lat:float,from_lng:float,to_lat:float,to_lng:float,_=Depends(manager)):
 if not (-90<=from_lat<=90 and -90<=to_lat<=90 and -180<=from_lng<=180 and -180<=to_lng<=180):err(422,'Invalid coordinates')
 return await route_between(from_lat,from_lng,to_lat,to_lng)

@app.get('/api/reports/attendance.pdf')
def attendance_pdf(driver_id:Optional[str]=None,start:Optional[str]=None,end:Optional[str]=None,s:Session=Depends(db),_=Depends(manager)):
 from reportlab.lib import colors
 from reportlab.lib.pagesizes import A4,landscape
 from reportlab.platypus import SimpleDocTemplate,Paragraph,Table,TableStyle,Spacer,KeepTogether
 from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
 from reportlab.lib.enums import TA_CENTER
 payload=attendance_report(driver_id,start,end,s)
 out=io.BytesIO();doc=SimpleDocTemplate(out,pagesize=landscape(A4),leftMargin=27,rightMargin=27,topMargin=32,bottomMargin=26)
 styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='SmallKriya',parent=styles['Normal'],fontSize=8,leading=11,textColor=colors.HexColor('#516680')))
 elements=[Paragraph('<b>KRIYA360 | Attendance Register</b>',styles['Title']),Paragraph(f"Driver: {driver_id or 'All drivers'} | From: {start or 'All'} | To: {end or 'All'} | Grace: {payload['grace_minutes']} minutes",styles['SmallKriya']),Spacer(1,13)]
 headings=['Driver','Date','Shift','Punch in (UTC)','Punch out (UTC)','Late min','Worked min','Status']
 data=[headings]
 from xml.sax.saxutils import escape
 for row in payload['records']:
  data.append([row['driver'][:22],row['date'],row['shift_expected'],(row['punch_in'] or '—')[:19],(row['punch_out'] or '—')[:19],str(row['late_minutes'] if row['late_minutes'] is not None else '—'),str(row['worked_minutes'] if row['worked_minutes'] is not None else '—'),row['status']])
 if len(data)==1:data.append(['No attendance records available']+['']*7)
 # Plain text cells are escaped to prevent raw markup in a report.
 table=Table(data,repeatRows=1,colWidths=[115,75,55,115,115,55,68,100],hAlign='LEFT')
 table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#092148')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,1),(-1,-1),'Helvetica'),('FONTSIZE',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),8),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f2f6fb')]),('LINEBELOW',(0,0),(-1,0),1,colors.HexColor('#f47a20'))]))
 elements.extend([table,Spacer(1,12),Paragraph('Attendance and GPS are driver-device-reported. Missing punch-ins require an approved shift roster and leave records to determine absences.',styles['SmallKriya'])])
 doc.build(elements);return Response(content=out.getvalue(),media_type='application/pdf',headers={'Content-Disposition':'attachment; filename="KRIYA360_attendance.pdf"'})
