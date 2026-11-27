"""Opt-in merchant marketplace. Separate credentials and audience protect legacy APIs.

No merchant is inserted into the existing users table, whose historical endpoints
assume every authenticated non-driver is a manager. All marketplace queries are
scoped to an approved merchant, assigned driver, or existing management role.
"""
from __future__ import annotations
import hashlib
import hmac
import math
import os
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
import jwt
from . import main as core

router = APIRouter(prefix='/api/marketplace', tags=['merchant marketplace'])
AUD = 'kriya360-merchant'

class Merchant(core.Base):
    __tablename__ = 'marketplace_merchants'
    id = Column(String, primary_key=True)
    email = Column(String(254), unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    name = Column(String(120), nullable=False)
    business_name = Column(String(160), nullable=False)
    business_type = Column(String(40), nullable=False)
    phone = Column(String(20), nullable=False)
    pickup_address = Column(String(500), nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    state = Column(String(24), nullable=False, default='pending')
    review_note = Column(String(500), nullable=False, default='')
    created_at = Column(DateTime(timezone=True), nullable=False)
    reviewed_at = Column(DateTime(timezone=True))
    reviewed_by = Column(String, ForeignKey('users.id'))
    session_version = Column(Integer, default=1, nullable=False)

class DriverDiscovery(core.Base):
    __tablename__ = 'marketplace_driver_discovery'
    driver_id = Column(String, ForeignKey('users.id'), primary_key=True)
    enabled = Column(Boolean, default=False, nullable=False)
    share_phone = Column(Boolean, default=False, nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)

class Booking(core.Base):
    __tablename__ = 'marketplace_bookings'
    __table_args__ = (UniqueConstraint('merchant_id','request_key',name='uq_marketplace_request_key'),)
    id = Column(String, primary_key=True)
    merchant_id = Column(String, ForeignKey('marketplace_merchants.id'), nullable=False, index=True)
    driver_id = Column(String, ForeignKey('users.id'), nullable=False, index=True)
    request_key = Column(String(100), nullable=False)
    title = Column(String(160), nullable=False)
    pickup_address = Column(String(500), nullable=False)
    pickup_lat = Column(Float, nullable=False)
    pickup_lng = Column(Float, nullable=False)
    delivery_address = Column(String(500), nullable=False)
    delivery_lat = Column(Float, nullable=False)
    delivery_lng = Column(Float, nullable=False)
    customer_name = Column(String(120), nullable=False)
    customer_phone = Column(String(20), nullable=False)
    instructions = Column(String(500), nullable=False, default='')
    weight_kg = Column(Float, nullable=False, default=0)
    due_at = Column(DateTime(timezone=True), nullable=False)
    state = Column(String(30), nullable=False, index=True, default='requested')
    created_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    accepted_at = Column(DateTime(timezone=True))
    arrived_at = Column(DateTime(timezone=True))
    pickup_at = Column(DateTime(timezone=True))
    pickup_nonce = Column(String, nullable=False, default='')
    pickup_attempts = Column(Integer, nullable=False, default=0)
    pickup_code_expires = Column(DateTime(timezone=True))
    task_id = Column(String, ForeignKey('tasks.id'), unique=True)
    shopify_order_id = Column(String(160), nullable=True)
    shopify_shop = Column(String(160), nullable=True)
    problem = Column(String(500), nullable=False, default='')

class Message(core.Base):
    __tablename__ = 'marketplace_messages'
    id = Column(String, primary_key=True)
    booking_id = Column(String, ForeignKey('marketplace_bookings.id'), nullable=False,index=True)
    sender_role = Column(String(12), nullable=False)
    body = Column(String(1000), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

class Audit(core.Base):
    __tablename__ = 'marketplace_audit'
    id = Column(String, primary_key=True)
    actor = Column(String, nullable=False)
    action = Column(String(60), nullable=False)
    target = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False,index=True)

class Throttle(core.Base):
    __tablename__ = 'marketplace_throttle'
    key = Column(String(64),primary_key=True)
    window = Column(Integer,nullable=False)
    count = Column(Integer,nullable=False)


def enabled():
    return os.getenv('KRIYA_MERCHANT_ENABLED','false').lower() == 'true'

def secret():
    value = os.getenv('KRIYA_MERCHANT_JWT_SECRET','')
    if len(value) < 32 or value == core.JWT_SECRET:
        core.err(503,'Merchant security configuration is incomplete')
    return value

def feature():
    if not enabled(): core.err(503,'Merchant services are not enabled yet')
    secret()

def audit(s,actor,action,target):
    s.add(Audit(id=str(uuid.uuid4()),actor=actor,action=action,target=target,created_at=core.now()))

def rate(s,key,limit,seconds=60):
    """Persistent fixed-window throttle. Separate transaction to retain failed attempts."""
    key=hashlib.sha256(key.encode()).hexdigest()
    window=int(core.now().timestamp())//seconds
    # Avoid committing business operations; this session is dedicated to throttling.
    with core.SessionLocal() as rs:
        row=rs.scalar(select(Throttle).where(Throttle.key==key).with_for_update())
        if row is None:
            row=Throttle(key=key,window=window,count=1);rs.add(row)
            try:rs.commit();return
            except IntegrityError:
                rs.rollback();row=rs.scalar(select(Throttle).where(Throttle.key==key).with_for_update())
                if row is None:core.err(503,'Please retry shortly')
        if row.window!=window:row.window=window;row.count=0
        if row.count>=limit:core.err(429,'Too many requests. Please try again shortly.')
        row.count+=1;rs.commit()

class MerchantRegister(BaseModel):
    name: str=Field(min_length=2,max_length=120)
    email: str=Field(max_length=254)
    password: str=Field(min_length=12,max_length=128)
    business_name: str=Field(min_length=2,max_length=160)
    business_type: str=Field(pattern='^(individual|retail|company|online)$')
    phone: str=Field(min_length=10,max_length=16)
    pickup_address: str=Field(min_length=5,max_length=500)
    lat: float=Field(ge=-90,le=90,allow_inf_nan=False)
    lng: float=Field(ge=-180,le=180,allow_inf_nan=False)
    consent: bool
    @field_validator('name','business_name','pickup_address')
    @classmethod
    def trim(cls,value):
        value=value.strip()
        if len(value)<2:raise ValueError('Required field')
        return value

class MerchantLogin(BaseModel):
    email:str=Field(max_length=254)
    password:str=Field(min_length=1,max_length=128)

class Review(BaseModel):
    state:str=Field(pattern='^(approved|rejected|suspended|pending)$')
    note:str=Field(min_length=3,max_length=500)

class Visibility(BaseModel):
    enabled:bool
    share_phone:bool=False

class BookingRequest(BaseModel):
    request_key:str=Field(min_length=16,max_length=100)
    driver_id:Optional[str]=Field(default=None,max_length=100)
    title:str=Field(min_length=2,max_length=160)
    delivery_address:str=Field(min_length=5,max_length=500)
    delivery_lat:float=Field(ge=-90,le=90,allow_inf_nan=False)
    delivery_lng:float=Field(ge=-180,le=180,allow_inf_nan=False)
    customer_name:str=Field(min_length=2,max_length=120)
    customer_phone:str=Field(min_length=10,max_length=16)
    due_at:datetime
    weight_kg:float=Field(default=0,ge=0,le=10000,allow_inf_nan=False)
    instructions:str=Field(default='',max_length=500)
    radius_km:float=Field(default=5,ge=1,le=20,allow_inf_nan=False)
    shopify_order_id:Optional[str]=Field(default=None,max_length=160)
    shopify_shop:Optional[str]=Field(default=None,max_length=160)

class PickupCode(BaseModel):
    code:str=Field(pattern=r'^\d{6}$')
    lat:float=Field(ge=-90,le=90,allow_inf_nan=False)
    lng:float=Field(ge=-180,le=180,allow_inf_nan=False)
    accuracy_m:float=Field(ge=0,le=100,allow_inf_nan=False)

class Problem(BaseModel):
    reason:str=Field(min_length=3,max_length=500)

class ChatBody(BaseModel):
    body:str=Field(min_length=1,max_length=1000)


def merchant_view(m):
    return {k:getattr(m,k) for k in ('id','email','name','business_name','business_type','phone','pickup_address','lat','lng','state','review_note')}

def merchant_token(m):
    return jwt.encode({'sub':m.id,'aud':AUD,'role':'merchant','sv':m.session_version,'iat':core.now(),'exp':core.now()+timedelta(hours=8)},secret(),algorithm='HS256')

def require_merchant(authorization:Optional[str]=Header(None),s:Session=Depends(core.db),_=Depends(feature)):
    if not authorization or not authorization.startswith('Bearer '):core.err(401,'Merchant login required')
    try:
        payload=jwt.decode(authorization[7:],secret(),algorithms=['HS256'],audience=AUD,options={'require':['exp','iat','sub','aud','sv']})
        if payload.get('role')!='merchant':raise ValueError()
    except (jwt.PyJWTError,ValueError,KeyError):core.err(401,'Merchant session expired. Sign in again.')
    m=s.get(Merchant,payload['sub'])
    if not m or payload['sv']!=m.session_version or m.state=='suspended':core.err(401,'Merchant account unavailable')
    return m

def approved(m=Depends(require_merchant)):
    if m.state!='approved':core.err(403,'Merchant approval is required')
    return m

@router.get('/health')
def health():return {'enabled':enabled(),'configured':enabled() and len(os.getenv('KRIYA_MERCHANT_JWT_SECRET',''))>=32}

@router.post('/auth/register',status_code=201)
def register(x:MerchantRegister,request:Request,s:Session=Depends(core.db),_=Depends(feature)):
    rate(s,'register-ip:'+str(request.client.host if request.client else 'unknown'),60,3600)
    email=core.normalized_email(x.email);rate(s,'register:'+email,3,3600)
    core.valid_password(x.password);phone=core.recipient_phone(x.phone)
    if not x.consent:core.err(422,'Accept the privacy and service terms to continue')
    m=Merchant(id=str(uuid.uuid4()),email=email,password_hash=core.hash_pin(x.password),name=x.name,business_name=x.business_name,business_type=x.business_type,phone=phone,pickup_address=x.pickup_address,lat=x.lat,lng=x.lng,state='pending',created_at=core.now())
    s.add(m);audit(s,m.id,'registered',m.id)
    try:s.commit()
    except IntegrityError:s.rollback();core.err(409,'Account already exists. Sign in instead.')
    return {'merchant':merchant_view(m),'access_token':merchant_token(m)}

@router.post('/auth/login')
def login(x:MerchantLogin,request:Request,s:Session=Depends(core.db),_=Depends(feature)):
    rate(s,'login-ip:'+str(request.client.host if request.client else 'unknown'),120,900)
    email=core.normalized_email(x.email);rate(s,'login:'+email,8,900)
    m=s.scalar(select(Merchant).where(Merchant.email==email))
    if not m or not core.check_pin(x.password,m.password_hash) or m.state=='suspended':core.err(401,'Invalid credentials or unavailable account')
    return {'merchant':merchant_view(m),'access_token':merchant_token(m)}

@router.get('/me')
def me(m=Depends(require_merchant)):return merchant_view(m)

@router.post('/auth/logout')
def logout(m=Depends(require_merchant),s:Session=Depends(core.db)):
    # Revoke all sessions for this merchant. Never touches driver sessions.
    row=s.scalar(select(Merchant).where(Merchant.id==m.id).with_for_update());row.session_version+=1;s.commit()
    return {'ok':True}

@router.get('/admin/merchants')
def admin_merchants(s:Session=Depends(core.db),_=Depends(core.manager),_f=Depends(feature)):
    return [merchant_view(m) for m in s.scalars(select(Merchant).order_by(Merchant.created_at.desc()).limit(500))]

@router.patch('/admin/merchants/{mid}')
def review(mid:str,x:Review,s:Session=Depends(core.db),u=Depends(core.manager),_f=Depends(feature)):
    m=s.scalar(select(Merchant).where(Merchant.id==mid).with_for_update())
    if not m:core.err(404,'Merchant not found')
    # Do not abandon in-transit packages. Resolve them first.
    if x.state!='approved' and s.scalar(select(Booking.id).where(Booking.merchant_id==mid,Booking.state.in_(['accepted','arrived','collected'])).limit(1)):
        active=[b for b in s.scalars(select(Booking).where(Booking.merchant_id==mid,Booking.state.in_(['accepted','arrived','collected']))) if booking_state(s,b)!='completed']
        if active:core.err(409,'Resolve active merchant deliveries before changing approval')
    m.state=x.state;m.review_note=x.note.strip();m.reviewed_at=core.now();m.reviewed_by=u.id
    if x.state=='suspended':m.session_version+=1
    audit(s,u.id,'merchant_'+x.state,mid);s.commit();return merchant_view(m)


def on_shift(u):return bool(u.shift_start and (not u.shift_end or core.naive(u.shift_start)>core.naive(u.shift_end)))

def pickup_reserved(s,driver_id):
    return bool(s.scalar(select(Booking.id).where(Booking.driver_id==driver_id,Booking.state.in_(['accepted','arrived'])).limit(1)))

def driver_eligible(s,u):
    if not u or u.role!='driver' or not u.active or not u.approved or not u.license_verified or not on_shift(u):return False
    opt=s.get(DriverDiscovery,u.id)
    if not opt or not opt.enabled or core.gps_freshness(u,core.now())[1]!='fresh':return False
    if u.lat is None or u.lng is None or not math.isfinite(u.lat) or not math.isfinite(u.lng):return False
    return not core.delivery_queue_state(s,u.id) and not pickup_reserved(s,u.id)

@router.get('/driver/visibility')
def visibility(u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    opt=s.get(DriverDiscovery,u.id)
    return {'enabled':bool(opt and opt.enabled),'share_phone':bool(opt and opt.share_phone),'eligible_now':driver_eligible(s,u)}

@router.put('/driver/visibility')
def set_visibility(x:Visibility,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    s.scalar(select(core.User).where(core.User.id==u.id).with_for_update())
    opt=s.get(DriverDiscovery,u.id)
    if not opt:opt=DriverDiscovery(driver_id=u.id);s.add(opt)
    opt.enabled=x.enabled;opt.share_phone=x.enabled and x.share_phone;opt.updated_at=core.now()
    audit(s,u.id,'discovery_changed',u.id);s.commit()
    return visibility(u,s,None)

def nearby_rows(s,m,radius):
    # Latitude bounding box avoids reading all drivers; exact range evaluated server-side.
    delta=radius/110.5
    q=select(core.User).join(DriverDiscovery,DriverDiscovery.driver_id==core.User.id).where(DriverDiscovery.enabled.is_(True),core.User.role=='driver',core.User.active.is_(True),core.User.approved.is_(True),core.User.license_verified.is_(True),core.User.lat.between(m.lat-delta,m.lat+delta)).limit(1000)
    rows=[]
    for u in s.scalars(q):
        if not driver_eligible(s,u):continue
        distance=core.haversine(m.lat,m.lng,u.lat,u.lng)
        if distance>radius:continue
        opt=s.get(DriverDiscovery,u.id)
        rows.append((distance,u,opt))
    return sorted(rows,key=lambda x:(x[0],x[1].id))[:50]

@router.get('/drivers/nearby')
def nearby(radius_km:float=5,vehicle:str='',favorites_only:bool=False,m=Depends(approved),s:Session=Depends(core.db)):
    if not math.isfinite(radius_km) or not 1<=radius_km<=20:core.err(422,'Search radius must be 1–20 km')
    rate(s,'nearby:'+m.id,30)
    saved=set(s.scalars(select(Favorite.driver_id).where(Favorite.merchant_id==m.id)))
    return [{'id':u.id,'name':u.name,'vehicle':u.vehicle,'verified':True,'distance_km':round(d*2)/2,'approx_lat':round(u.lat,2),'approx_lng':round(u.lng,2),'contact_available':opt.share_phone,'favorite':u.id in saved,**driver_reputation(s,u.id)} for d,u,opt in nearby_rows(s,m,radius_km) if (not vehicle or (u.vehicle or '').casefold()==vehicle.casefold()) and (not favorites_only or u.id in saved)]

@router.get('/drivers/{did}/contact')
def contact(did:str,m=Depends(approved),s:Session=Depends(core.db)):
    rate(s,'contact:'+m.id,15,3600)
    u=s.get(core.User,did);opt=s.get(DriverDiscovery,did)
    if not driver_eligible(s,u) or not opt.share_phone or core.haversine(m.lat,m.lng,u.lat,u.lng)>20:core.err(404,'Driver contact unavailable')
    audit(s,m.id,'contact_revealed',did);s.commit()
    return {'phone':u.phone,'name':u.name}


def booking_state(s,b):
    if b.state=='requested' and core.naive(b.expires_at)<=core.naive(core.now()):return 'expired'
    if b.state=='collected' and b.task_id:
        t=s.get(core.Task,b.task_id)
        if t and t.status=='completed':return 'completed'
        if t and t.status=='in_progress':return 'in_transit'
    return b.state

def pickup_code(b):
    raw=hmac.new(secret().encode(),('pickup:'+b.id+':'+b.pickup_nonce).encode(),hashlib.sha256).digest()
    return str(int.from_bytes(raw[:8],'big')%1000000).zfill(6)

def booking_view(s,b,role):
    state=booking_state(s,b)
    d=s.get(core.User,b.driver_id);m=s.get(Merchant,b.merchant_id)
    data={k:getattr(b,k) for k in ('id','merchant_id','driver_id','title','pickup_address','pickup_lat','pickup_lng','delivery_address','delivery_lat','delivery_lng','instructions','weight_kg','task_id','problem','shopify_order_id','shopify_shop')}
    data.update(state=state,created_at=core.iso(b.created_at),expires_at=core.iso(b.expires_at),due_at=core.iso(b.due_at),driver_name=d.name if d else '',merchant_name=m.business_name if m else '')
    if role in ('merchant','manager'):data.update(customer_name=b.customer_name,customer_phone=b.customer_phone)
    if state in ('accepted','arrived','collected','in_transit'):
        if role=='driver' and m:data['merchant_phone']=m.phone
        if role=='merchant' and d:
            opt=s.get(DriverDiscovery,d.id)
            if opt and opt.share_phone:data['driver_phone']=d.phone
            if core.gps_freshness(d,core.now())[1]=='fresh':data['driver_location']={'lat':d.lat,'lng':d.lng}
    if role=='merchant' and state in ('accepted','arrived') and b.pickup_nonce and b.pickup_code_expires and core.naive(b.pickup_code_expires)>core.naive(core.now()) and b.pickup_attempts<5:
        data['pickup_code']=pickup_code(b)
    if role in ('merchant','driver'):data['rating_given']=s.get(Rating,(b.id,role)) is not None
    return data

@router.post('/bookings',status_code=201)
def create_booking(x:BookingRequest,m=Depends(approved),s:Session=Depends(core.db)):
    rate(s,'booking:'+m.id,20,3600)
    # Return the same booking after a timeout/retry, rather than making another request.
    old=s.scalar(select(Booking).where(Booking.merchant_id==m.id,Booking.request_key==x.request_key))
    if old:return booking_view(s,old,'merchant')
    m=s.scalar(select(Merchant).where(Merchant.id==m.id).with_for_update().execution_options(populate_existing=True))
    if m.state!='approved':core.err(403,'Merchant approval required')
    if x.due_at.tzinfo is None or not core.now()<x.due_at<core.now()+timedelta(days=7):core.err(422,'Use a future delivery deadline within seven days')
    core.recipient_phone(x.customer_phone)
    if not x.title.strip() or not x.delivery_address.strip() or not x.customer_name.strip():core.err(422,'Complete all delivery details')
    if x.shopify_order_id or x.shopify_shop:
        from .shopify_marketplace import validate_order_reference
        validate_order_reference(s,m,x.shopify_shop,x.shopify_order_id)
    choices=nearby_rows(s,m,x.radius_km)
    if x.driver_id:choices=[z for z in choices if z[1].id==x.driver_id]
    if not choices:core.err(409,'No eligible nearby driver. Refresh or widen your search.')
    d=choices[0][1]
    pending=s.scalar(select(func.count()).select_from(Booking).where(Booking.merchant_id==m.id,Booking.state=='requested',Booking.expires_at>core.now()))
    if pending>=10:core.err(429,'Too many pending pickup requests')
    b=Booking(id=str(uuid.uuid4()),merchant_id=m.id,driver_id=d.id,request_key=x.request_key,title=x.title.strip(),pickup_address=m.pickup_address,pickup_lat=m.lat,pickup_lng=m.lng,delivery_address=x.delivery_address.strip(),delivery_lat=x.delivery_lat,delivery_lng=x.delivery_lng,customer_name=x.customer_name.strip(),customer_phone=x.customer_phone,instructions=x.instructions.strip(),weight_kg=x.weight_kg,due_at=x.due_at,state='requested',created_at=core.now(),expires_at=min(core.now()+timedelta(minutes=5),x.due_at),shopify_order_id=x.shopify_order_id,shopify_shop=x.shopify_shop)
    s.add(b);audit(s,m.id,'booking_requested',b.id)
    try:s.commit()
    except IntegrityError:
        s.rollback();old=s.scalar(select(Booking).where(Booking.merchant_id==m.id,Booking.request_key==x.request_key))
        if old:return booking_view(s,old,'merchant')
        core.err(409,'Booking conflict. Refresh and retry.')
    return booking_view(s,b,'merchant')

@router.get('/bookings')
def merchant_bookings(m=Depends(approved),s:Session=Depends(core.db)):
    return [booking_view(s,b,'merchant') for b in s.scalars(select(Booking).where(Booking.merchant_id==m.id).order_by(Booking.created_at.desc()).limit(200))]

@router.get('/driver/bookings')
def driver_bookings(u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    return [booking_view(s,b,'driver') for b in s.scalars(select(Booking).where(Booking.driver_id==u.id).order_by(Booking.created_at.desc()).limit(200))]

@router.get('/admin/bookings')
def admin_bookings(s:Session=Depends(core.db),_=Depends(core.manager),_f=Depends(feature)):
    return [booking_view(s,b,'manager') for b in s.scalars(select(Booking).order_by(Booking.created_at.desc()).limit(500))]

def driver_booking_lock(s,u,bid):
    # All existing manager assignment entry points also lock the driver first.
    locked=s.scalar(select(core.User).where(core.User.id==u.id).with_for_update().execution_options(populate_existing=True))
    b=s.scalar(select(Booking).where(Booking.id==bid,Booking.driver_id==u.id).with_for_update())
    if not b:core.err(404,'Booking not found')
    return locked,b

@router.post('/driver/bookings/{bid}/accept')
def accept_booking(bid:str,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    d,b=driver_booking_lock(s,u,bid)
    if booking_state(s,b)!='requested':core.err(409,'Pickup request is no longer available')
    m=s.scalar(select(Merchant).where(Merchant.id==b.merchant_id).with_for_update().execution_options(populate_existing=True))
    if not m or m.state!='approved' or not driver_eligible(s,d):core.err(409,'Driver or merchant unavailable. Check current tasks and GPS.')
    from .shopify_marketplace import require_active_order
    require_active_order(s,b)
    b.state='accepted';b.accepted_at=core.now();b.pickup_nonce=secrets.token_hex(24);b.pickup_attempts=0;b.pickup_code_expires=min(core.now()+timedelta(hours=2),b.due_at if b.due_at.tzinfo else b.due_at.replace(tzinfo=core.timezone.utc))
    audit(s,u.id,'booking_accepted',bid);s.commit();return booking_view(s,b,'driver')

@router.post('/driver/bookings/{bid}/reject')
def reject_booking(bid:str,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    _,b=driver_booking_lock(s,u,bid)
    if booking_state(s,b)!='requested':core.err(409,'Only pending requests can be rejected')
    b.state='rejected';audit(s,u.id,'booking_rejected',bid);s.commit();return booking_view(s,b,'driver')

@router.post('/driver/bookings/{bid}/arrive')
def arrive_booking(bid:str,x:core.Coords,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    _,b=driver_booking_lock(s,u,bid)
    if b.state!='accepted':core.err(409,'Accept pickup first')
    if x.accuracy_m is None or x.accuracy_m>100 or not all(math.isfinite(v) for v in (x.lat,x.lng,x.accuracy_m)) or core.haversine(x.lat,x.lng,b.pickup_lat,b.pickup_lng)>0.25:core.err(422,'A reliable GPS fix within 250 metres of pickup is required')
    b.state='arrived';b.arrived_at=core.now();audit(s,u.id,'pickup_arrived',bid);s.commit();return booking_view(s,b,'driver')

@router.post('/driver/bookings/{bid}/collect')
def collect_booking(bid:str,x:PickupCode,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    d,b=driver_booking_lock(s,u,bid)
    if b.state=='collected' and b.task_id:return booking_view(s,b,'driver')
    if b.state!='arrived':core.err(409,'Confirm arrival before pickup')
    from .shopify_marketplace import require_active_order
    require_active_order(s,b)
    if not on_shift(d) or core.delivery_queue_state(s,d.id):core.err(409,'Driver has another delivery or is off shift. Contact management.')
    if core.haversine(x.lat,x.lng,b.pickup_lat,b.pickup_lng)>0.25:core.err(422,'Confirm pickup at the merchant location')
    if not b.pickup_code_expires or core.naive(b.pickup_code_expires)<=core.naive(core.now()) or b.pickup_attempts>=5:core.err(409,'Pickup code expired or locked. Ask merchant to renew it.')
    if not hmac.compare_digest(x.code,pickup_code(b)):
        b.pickup_attempts+=1;s.commit();core.err(400,'Incorrect pickup code')
    # Reuse the existing recipient OTP/photo delivery, route, tracking and completion APIs.
    t=core.Task(id=str(uuid.uuid4()),title=b.title,address=b.delivery_address,lat=b.delivery_lat,lng=b.delivery_lng,driver_id=d.id,status='assigned',customer=b.customer_name,customer_phone=b.customer_phone,instructions='Merchant pickup verified. '+b.instructions,due_at=b.due_at,assigned_at=core.now())
    s.add(t);s.flush();b.task_id=t.id;b.state='collected';b.pickup_at=core.now();b.pickup_nonce='';audit(s,u.id,'pickup_verified',bid);s.commit();return booking_view(s,b,'driver')

@router.post('/bookings/{bid}/renew-code')
def renew_code(bid:str,m=Depends(approved),s:Session=Depends(core.db)):
    rate(s,'pickup-code:'+m.id,5,3600)
    b=s.scalar(select(Booking).where(Booking.id==bid,Booking.merchant_id==m.id).with_for_update())
    if not b:core.err(404,'Booking not found')
    if b.state not in ('accepted','arrived'):core.err(409,'Pickup code cannot be renewed')
    b.pickup_nonce=secrets.token_hex(24);b.pickup_attempts=0;b.pickup_code_expires=core.now()+timedelta(hours=2);audit(s,m.id,'pickup_code_renewed',bid);s.commit();return booking_view(s,b,'merchant')

@router.post('/bookings/{bid}/cancel')
def cancel_booking(bid:str,m=Depends(approved),s:Session=Depends(core.db)):
    b=s.scalar(select(Booking).where(Booking.id==bid,Booking.merchant_id==m.id))
    if not b:core.err(404,'Booking not found')
    s.scalar(select(core.User).where(core.User.id==b.driver_id).with_for_update())
    b=s.scalar(select(Booking).where(Booking.id==bid,Booking.merchant_id==m.id).with_for_update().execution_options(populate_existing=True))
    if b.state not in ('requested','accepted','arrived'):core.err(409,'Cannot cancel after package collection')
    b.state='cancelled';b.pickup_nonce='';audit(s,m.id,'booking_cancelled',bid);s.commit();return booking_view(s,b,'merchant')

@router.post('/driver/bookings/{bid}/problem')
def driver_problem(bid:str,x:Problem,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):
    _,b=driver_booking_lock(s,u,bid)
    if booking_state(s,b) not in ('accepted','arrived','collected','in_transit'):core.err(409,'No active pickup')
    b.problem=x.reason.strip();audit(s,u.id,'booking_problem',bid);s.commit();return booking_view(s,b,'driver')

@router.post('/admin/bookings/{bid}/cancel-pickup')
def admin_cancel(bid:str,x:Problem,u=Depends(core.manager),s:Session=Depends(core.db),_f=Depends(feature)):
    b=s.get(Booking,bid)
    if not b:core.err(404,'Booking not found')
    s.scalar(select(core.User).where(core.User.id==b.driver_id).with_for_update())
    b=s.scalar(select(Booking).where(Booking.id==bid).with_for_update().execution_options(populate_existing=True))
    if b.state not in ('requested','accepted','arrived'):core.err(409,'Collected packages require managed resolution')
    b.state='cancelled';b.problem=x.reason;b.pickup_nonce='';audit(s,u.id,'manager_cancelled_pickup',bid);s.commit();return booking_view(s,b,'manager')


def chat_booking(s,bid,role,uid):
    col=Booking.merchant_id if role=='merchant' else Booking.driver_id
    b=s.scalar(select(Booking).where(Booking.id==bid,col==uid))
    if not b:core.err(404,'Booking not found')
    return b

def read_chat(s,b):
    return [{'id':r.id,'sender_role':r.sender_role,'body':r.body,'created_at':core.iso(r.created_at)} for r in reversed(list(s.scalars(select(Message).where(Message.booking_id==b.id).order_by(Message.created_at.desc()).limit(100))))]

def write_chat(s,b,role,uid,x):
    if booking_state(s,b) not in ('requested','accepted','arrived','collected','in_transit'):core.err(409,'This conversation is closed')
    if not x.body.strip():core.err(422,'Message is empty')
    rate(s,'chat:'+role+':'+uid,30)
    r=Message(id=str(uuid.uuid4()),booking_id=b.id,sender_role=role,body=x.body.strip(),created_at=core.now());s.add(r);s.commit();return {'id':r.id}

@router.get('/bookings/{bid}/messages')
def merchant_chat(bid:str,m=Depends(approved),s:Session=Depends(core.db)):return read_chat(s,chat_booking(s,bid,'merchant',m.id))
@router.post('/bookings/{bid}/messages')
def merchant_message(bid:str,x:ChatBody,m=Depends(approved),s:Session=Depends(core.db)):return write_chat(s,chat_booking(s,bid,'merchant',m.id),'merchant',m.id,x)
@router.get('/driver/bookings/{bid}/messages')
def driver_chat(bid:str,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):return read_chat(s,chat_booking(s,bid,'driver',u.id))
@router.post('/driver/bookings/{bid}/messages')
def driver_message(bid:str,x:ChatBody,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):return write_chat(s,chat_booking(s,bid,'driver',u.id),'driver',u.id,x)


def driver_alerts(s,u):
    if not enabled():return []
    return [{'id':'merchant-pickup-'+b.id,'type':'merchant_pickup','title':'New merchant pickup request','message':b.title+' • Open Merchant pickups','at':core.iso(b.created_at)} for b in s.scalars(select(Booking).where(Booking.driver_id==u.id,Booking.state=='requested',Booking.expires_at>core.now()))]

class PickupLocation(BaseModel):
    address:str=Field(min_length=5,max_length=500)
    lat:float=Field(ge=-90,le=90,allow_inf_nan=False)
    lng:float=Field(ge=-180,le=180,allow_inf_nan=False)

@router.put('/me/pickup')
def change_pickup(x:PickupLocation,m=Depends(approved),s:Session=Depends(core.db)):
    rate(s,'pickup-location:'+m.id,12,86400)
    row=s.scalar(select(Merchant).where(Merchant.id==m.id).with_for_update().execution_options(populate_existing=True))
    if row.state!='approved':core.err(403,'Merchant approval required')
    if len(x.address.strip())<5:core.err(422,'Enter the pickup address')
    row.pickup_address=x.address.strip();row.lat=x.lat;row.lng=x.lng
    audit(s,m.id,'pickup_location_changed',m.id);s.commit();return merchant_view(row)

class Favorite(core.Base):
    __tablename__='marketplace_favorites'
    merchant_id=Column(String,ForeignKey('marketplace_merchants.id'),primary_key=True)
    driver_id=Column(String,ForeignKey('users.id'),primary_key=True)
    created_at=Column(DateTime(timezone=True),nullable=False)

class Rating(core.Base):
    __tablename__='marketplace_ratings'
    booking_id=Column(String,ForeignKey('marketplace_bookings.id'),primary_key=True)
    rater_role=Column(String(12),primary_key=True)
    stars=Column(Integer,nullable=False)
    comment=Column(String(500),nullable=False,default='')
    created_at=Column(DateTime(timezone=True),nullable=False)

class TrackingLink(core.Base):
    __tablename__='marketplace_tracking_links'
    booking_id=Column(String,ForeignKey('marketplace_bookings.id'),primary_key=True)
    token_hash=Column(String(64),unique=True,nullable=False,index=True)
    expires_at=Column(DateTime(timezone=True),nullable=False)

class FavoriteInput(BaseModel):
    saved:bool

class RatingInput(BaseModel):
    stars:int=Field(ge=1,le=5,strict=True)
    comment:str=Field(default='',max_length=500)

class TrackingInput(BaseModel):
    token:str=Field(min_length=40,max_length=100,pattern=r'^[A-Za-z0-9_-]+$')


def driver_reputation(s,did):
    completed=s.scalar(select(func.count()).select_from(Booking).join(core.Task,core.Task.id==Booking.task_id).where(Booking.driver_id==did,core.Task.status=='completed')) or 0
    avg,count=s.execute(select(func.avg(Rating.stars),func.count(Rating.stars)).join(Booking,Booking.id==Rating.booking_id).where(Booking.driver_id==did,Rating.rater_role=='merchant')).one()
    return {'completed_deliveries':completed,'rating':round(float(avg),1) if avg is not None else None,'rating_count':count}

@router.put('/drivers/{did}/favorite')
def favorite(did:str,x:FavoriteInput,m=Depends(approved),s:Session=Depends(core.db)):
    row=s.get(Favorite,(m.id,did))
    if x.saved and not row:
        u=s.get(core.User,did)
        if not driver_eligible(s,u) or core.haversine(m.lat,m.lng,u.lat,u.lng)>20:core.err(404,'Driver unavailable')
        s.add(Favorite(merchant_id=m.id,driver_id=did,created_at=core.now()))
    elif not x.saved and row:s.delete(row)
    try:s.commit()
    except IntegrityError:s.rollback()
    return {'saved':x.saved}

@router.get('/favorites')
def favorites(m=Depends(approved),s:Session=Depends(core.db)):
    rows=s.execute(select(Favorite,core.User).join(core.User,core.User.id==Favorite.driver_id).where(Favorite.merchant_id==m.id).limit(100)).all()
    # Saved drivers remain visible as directory entries only; no offline location or contact is returned.
    return [{'id':u.id,'name':u.name,'vehicle':u.vehicle,'available':driver_eligible(s,u) and core.haversine(m.lat,m.lng,u.lat,u.lng)<=20} for f,u in rows if u.active and u.approved]


def submit_rating(s,b,role,x):
    if booking_state(s,b)!='completed':core.err(409,'Rate after delivery is completed')
    if s.get(Rating,(b.id,role)):core.err(409,'This delivery has already been rated')
    row=Rating(booking_id=b.id,rater_role=role,stars=x.stars,comment=x.comment.strip(),created_at=core.now());s.add(row)
    try:s.commit()
    except IntegrityError:s.rollback();core.err(409,'This delivery has already been rated')
    return {'stars':row.stars}

@router.post('/bookings/{bid}/rating')
def merchant_rating(bid:str,x:RatingInput,m=Depends(approved),s:Session=Depends(core.db)):return submit_rating(s,chat_booking(s,bid,'merchant',m.id),'merchant',x)

@router.post('/driver/bookings/{bid}/rating')
def driver_rating(bid:str,x:RatingInput,u=Depends(core.driver),s:Session=Depends(core.db),_f=Depends(feature)):return submit_rating(s,chat_booking(s,bid,'driver',u.id),'driver',x)

@router.post('/bookings/{bid}/tracking-link')
def tracking_link(bid:str,m=Depends(approved),s:Session=Depends(core.db)):
    from urllib.parse import urlsplit
    rate(s,'tracking-link:'+m.id,20,3600)
    b=chat_booking(s,bid,'merchant',m.id)
    if booking_state(s,b) in ('cancelled','rejected','expired'):core.err(409,'Pickup is no longer active')
    origin=os.getenv('KRIYA_TRACKING_FRONTEND_URL','https://kriya360-dashboard.onrender.com').rstrip('/')
    url=urlsplit(origin)
    if url.scheme!='https' or not url.hostname or url.username or url.password or url.query or url.fragment or url.path:core.err(503,'Tracking frontend is not configured')
    token=secrets.token_urlsafe(32);token_hash=hashlib.sha256(token.encode()).hexdigest()
    row=s.scalar(select(TrackingLink).where(TrackingLink.booking_id==b.id).with_for_update())
    if not row:row=TrackingLink(booking_id=b.id);s.add(row)
    row.token_hash=token_hash;row.expires_at=core.now()+timedelta(days=7)
    audit(s,m.id,'tracking_link_issued',bid);s.commit()
    return {'url':origin+'/#track='+token,'expires_at':core.iso(row.expires_at)}

@router.post('/track/lookup')
def public_tracking(x:TrackingInput,request:Request,s:Session=Depends(core.db),_f=Depends(feature)):
    # Public capability exposes only coarse delivery status, never contact, exact location or order details.
    rate(s,'public-track:'+str(request.client.host if request.client else 'unknown'),300)
    token_hash=hashlib.sha256(x.token.encode()).hexdigest()
    row=s.scalar(select(TrackingLink).where(TrackingLink.token_hash==token_hash))
    if not row or core.naive(row.expires_at)<=core.naive(core.now()):core.err(404,'Tracking link expired or invalid')
    b=s.get(Booking,row.booking_id)
    if not b:core.err(404,'Tracking link expired or invalid')
    return {'state':booking_state(s,b),'expires_at':core.iso(row.expires_at)}
