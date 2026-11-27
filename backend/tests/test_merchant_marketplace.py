"""Isolated regression and marketplace contract tests; no external services."""
import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
import base64
import hashlib
import hmac
import json
import uuid
from datetime import timedelta
from io import BytesIO
from urllib.parse import parse_qs,urlsplit
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from app import main as core
from app import marketplace as mp
from app import shopify_marketplace as shopify

assert str(core.engine.url)=='sqlite://', 'Marketplace tests require an isolated in-memory SQLite database'
c=TestClient(core.app,base_url='https://testserver')

def auth(token):return {'Authorization':'Bearer '+token}

@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv('KRIYA_MERCHANT_ENABLED','true')
    monkeypatch.setenv('KRIYA_MERCHANT_JWT_SECRET','test-merchant-secret-only-for-isolated-regressions-2026')
    monkeypatch.setenv('SHOPIFY_ENABLED','false')
    # Unique test identities do not interfere with legacy fixtures.
    uid=uuid.uuid4().hex
    with core.SessionLocal() as s:
        manager=core.User(id='manager-'+uid,role='manager',name='Test manager',phone='8'+str(int(uid[:12],16)).zfill(9)[-9:],pin_hash=core.hash_pin('1234'),approved=True,active=True)
        driver=core.User(id='driver-'+uid,role='driver',name='Test delivery driver',phone='7'+str(int(uid[:12],16)).zfill(9)[-9:],pin_hash=core.hash_pin('1234'),approved=True,active=True,license_verified=True,vehicle='Bike',shift_start=core.now(),lat=12.9732,lng=77.5958,last_gps=core.now(),last_gps_received_at=core.now())
        s.add_all([manager,driver]);s.commit()
        result={'manager':auth(core.token(manager)),'driver':auth(core.token(driver)),'driver_id':driver.id,'driver_phone':driver.phone,'id':uid}
    yield result
    # Clear active reservations and mark driver off-shift so fixtures do not leak eligibility.
    with core.SessionLocal() as s:
        for b in s.scalars(select(mp.Booking).where(mp.Booking.driver_id==result['driver_id'])):
            if b.state in ('requested','accepted','arrived'):b.state='cancelled'
        u=s.get(core.User,result['driver_id']);u.shift_end=core.now();u.active=False;s.commit()

def register(cfg,suffix):
    payload={'name':'Pilot seller','email':cfg['id']+suffix+'@example.test','password':'PilotTestPassword123','business_name':'Pilot store '+suffix,'business_type':'individual','phone':'9876543210','pickup_address':'Test pickup address Bengaluru','lat':12.9716,'lng':77.5946,'consent':True}
    r=c.post('/api/marketplace/auth/register',json=payload);assert r.status_code==201,r.text
    result=r.json();return result['merchant']['id'],auth(result['access_token']),payload

def approve(cfg,mid):
    r=c.patch('/api/marketplace/admin/merchants/'+mid,headers=cfg['manager'],json={'state':'approved','note':'Contact and business independently reviewed for test'})
    assert r.status_code==200,r.text

def visibility(cfg,share=True):
    r=c.put('/api/marketplace/driver/visibility',headers=cfg['driver'],json={'enabled':True,'share_phone':share})
    assert r.status_code==200,r.text;return r.json()

def booking_body(cfg,**extra):
    return {'request_key':uuid.uuid4().hex,'driver_id':cfg['driver_id'],'title':'Test merchant parcel','delivery_address':'Test destination Bengaluru','delivery_lat':12.98,'delivery_lng':77.6,'customer_name':'Test customer','customer_phone':'9876543210','due_at':(core.now()+timedelta(hours=3)).isoformat(),'weight_kg':1.5,'radius_km':5,**extra}

def create_booking(cfg,m,body=None):
    r=c.post('/api/marketplace/bookings',headers=m,json=body or booking_body(cfg));assert r.status_code==201,r.text;return r.json()

def test_marketplace_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv('KRIYA_MERCHANT_ENABLED',raising=False)
    assert c.get('/api/marketplace/health').json()['enabled'] is False
    r=c.post('/api/marketplace/auth/login',json={'email':'test@example.test','password':'a'})
    assert r.status_code==503

def test_merchant_auth_isolation_and_approval(configured):
    cfg=configured;mid,m,payload=register(cfg,'isolation')
    assert c.get('/api/marketplace/me',headers=m).json()['state']=='pending'
    assert c.get('/api/marketplace/drivers/nearby',headers=m).status_code==403
    for path in ('/api/tasks','/api/drivers','/api/me','/api/expenses','/api/marketplace/admin/merchants','/api/marketplace/driver/bookings'):
        assert c.get(path,headers=m).status_code in (401,403),path
    assert c.get('/api/marketplace/me',headers=cfg['driver']).status_code==401
    assert c.patch('/api/marketplace/admin/merchants/'+mid,headers=cfg['driver'],json={'state':'approved','note':'Unauthorized review'}).status_code==403
    approve(cfg,mid)
    assert c.get('/api/marketplace/drivers/nearby',headers=m).status_code==200
    logged=c.post('/api/marketplace/auth/login',json={'email':payload['email'],'password':payload['password']});assert logged.status_code==200
    assert c.post('/api/marketplace/auth/logout',headers=m).status_code==200
    assert c.get('/api/marketplace/me',headers=auth(logged.json()['access_token'])).status_code==401

def test_discovery_requires_consent_fresh_gps_and_radius(configured):
    cfg=configured;mid,m,_=register(cfg,'discovery');approve(cfg,mid)
    assert cfg['driver_id'] not in [x['id'] for x in c.get('/api/marketplace/drivers/nearby',headers=m).json()]
    assert visibility(cfg,False)['eligible_now']
    r=c.get('/api/marketplace/drivers/nearby?radius_km=1',headers=m);assert r.status_code==200
    row=next(x for x in r.json() if x['id']==cfg['driver_id'])
    assert 'phone' not in row and 'lat' not in row and row['approx_lat']==round(12.9732,2) and not row['contact_available']
    path='/api/marketplace/drivers/'+cfg['driver_id']+'/contact'
    assert c.get(path,headers=m).status_code==404
    visibility(cfg,True)
    assert c.get(path,headers=m).json()['phone']==cfg['driver_phone']
    with core.SessionLocal() as s:
        u=s.get(core.User,cfg['driver_id']);u.last_gps_received_at=core.now()-timedelta(minutes=3);s.commit()
    assert c.get(path,headers=m).status_code==404
    assert cfg['driver_id'] not in [x['id'] for x in c.get('/api/marketplace/drivers/nearby',headers=m).json()]
    assert c.get('/api/marketplace/drivers/nearby?radius_km=100',headers=m).status_code==422

def test_booking_pickup_and_existing_delivery_contract(configured):
    cfg=configured;mid,m,_=register(cfg,'booking');approve(cfg,mid);other_id,other,_=register(cfg,'other');approve(cfg,other_id);visibility(cfg)
    fav='/api/marketplace/drivers/'+cfg['driver_id']+'/favorite'
    assert c.put(fav,headers=m,json={'saved':True}).json()['saved']
    assert any(x['id']==cfg['driver_id'] and x['favorite'] for x in c.get('/api/marketplace/drivers/nearby?favorites_only=true',headers=m).json())
    assert c.get('/api/marketplace/favorites',headers=other).json()==[]
    body=booking_body(cfg);b=create_booking(cfg,m,body);bid=b['id'];assert b['state']=='requested'
    assert c.post('/api/marketplace/bookings/'+bid+'/rating',headers=m,json={'stars':5}).status_code==409
    link=c.post('/api/marketplace/bookings/'+bid+'/tracking-link',headers=m);assert link.status_code==200,link.text
    track_token=link.json()['url'].split('#track=')[1]
    public=c.post('/api/marketplace/track/lookup',json={'token':track_token});assert public.status_code==200 and set(public.json())=={'state','expires_at'}
    assert create_booking(cfg,m,body)['id']==bid
    assert c.get('/api/marketplace/bookings',headers=other).json()==[]
    assert c.post('/api/marketplace/bookings/'+bid+'/cancel',headers=other).status_code==404
    assert c.get('/api/marketplace/bookings/'+bid+'/messages',headers=other).status_code==404
    assert any(n['id']=='merchant-pickup-'+bid for n in c.get('/api/driver/notifications',headers=cfg['driver']).json())
    path='/api/marketplace/driver/bookings/'+bid
    r=c.post(path+'/accept',headers=cfg['driver']);assert r.status_code==200,r.text;assert r.json()['state']=='accepted' and 'pickup_code' not in r.json()
    merchant_view=c.get('/api/marketplace/bookings',headers=m).json()[0];code=merchant_view['pickup_code'];assert len(code)==6 and 'driver_location' in merchant_view
    assert c.post(path+'/accept',headers=cfg['driver']).status_code==409
    assert c.get('/api/marketplace/drivers/nearby',headers=m).json()==[] or cfg['driver_id'] not in [x['id'] for x in c.get('/api/marketplace/drivers/nearby',headers=m).json()]
    # Existing manager assignment must not conflict with an accepted pickup.
    r=c.post('/api/tasks',headers=cfg['manager'],json={'title':'Conflicting assignment','driver_id':cfg['driver_id'],'address':'Test destination','lat':12.98,'lng':77.6,'due_at':body['due_at'],'customer':'Test recipient','customer_phone':'9876543210'});assert r.status_code==409,r.text
    r=c.post('/api/attendance/punch-out',headers=cfg['driver'],json={'lat':12.9716,'lng':77.5946});assert r.status_code==409,r.text
    assert c.post('/api/marketplace/bookings/'+bid+'/messages',headers=m,json={'body':'Package ready'}).status_code==200
    assert c.get(path+'/messages',headers=cfg['driver']).json()[0]['body']=='Package ready'
    assert c.post(path+'/arrive',headers=cfg['driver'],json={'lat':14.0,'lng':77.5946,'accuracy_m':10}).status_code==422
    gps={'lat':12.9716,'lng':77.5946,'accuracy_m':10}
    r=c.post(path+'/arrive',headers=cfg['driver'],json=gps);assert r.status_code==200,r.text
    wrong='000000' if code!='000000' else '111111'
    r=c.post(path+'/collect',headers=cfg['driver'],json={**gps,'code':wrong});assert r.status_code==400,r.text
    r=c.post(path+'/collect',headers=cfg['driver'],json={**gps,'code':code});assert r.status_code==200,r.text
    collected=r.json();tid=collected['task_id'];assert tid and collected['state']=='collected'
    assert c.post(path+'/collect',headers=cfg['driver'],json={**gps,'code':code}).json()['task_id']==tid
    assert c.post('/api/marketplace/bookings/'+bid+'/cancel',headers=m).status_code==409
    assert len([x for x in c.get('/api/tasks',headers=cfg['driver']).json() if x['id']==tid])==1
    r=c.post('/api/tasks/'+tid+'/start',headers=cfg['driver']);assert r.status_code==200,r.text
    assert c.get('/api/marketplace/bookings',headers=m).json()[0]['state']=='in_transit'
    with core.SessionLocal() as s:
        task=s.get(core.Task,tid);task.otp_hash=core.hash_pin('123456');task.otp_expires=core.now()+timedelta(minutes=10);s.commit()
    im=Image.new('RGB',(24,24),'blue');buffer=BytesIO();im.save(buffer,'PNG')
    r=c.post('/api/tasks/'+tid+'/complete',headers=cfg['driver'],data={'otp':'123456'},files={'image':('proof.png',buffer.getvalue(),'image/png')});assert r.status_code==200,r.text
    view=c.get('/api/marketplace/bookings',headers=m).json()[0];assert view['state']=='completed' and 'driver_location' not in view and 'pickup_code' not in view
    assert c.post('/api/marketplace/bookings/'+bid+'/rating',headers=m,json={'stars':5}).status_code==200
    assert c.post('/api/marketplace/bookings/'+bid+'/rating',headers=m,json={'stars':1}).status_code==409
    assert c.post(path+'/rating',headers=cfg['driver'],json={'stars':4}).status_code==200
    assert c.post('/api/marketplace/track/lookup',json={'token':track_token}).json()['state']=='completed'
    new_link=c.post('/api/marketplace/bookings/'+bid+'/tracking-link',headers=m).json()['url'].split('#track=')[1]
    assert new_link!=track_token and c.post('/api/marketplace/track/lookup',json={'token':track_token}).status_code==404
    with core.SessionLocal() as s:assert mp.driver_reputation(s,cfg['driver_id'])=={'completed_deliveries':1,'rating':5.0,'rating_count':1}

def test_expired_and_cancelled_pickups(configured):
    cfg=configured;mid,m,_=register(cfg,'expiry');approve(cfg,mid);visibility(cfg)
    b=create_booking(cfg,m);bid=b['id']
    with core.SessionLocal() as s:
        row=s.get(mp.Booking,bid);row.expires_at=core.now()-timedelta(seconds=10);s.commit()
    assert c.post('/api/marketplace/driver/bookings/'+bid+'/accept',headers=cfg['driver']).status_code==409
    assert c.get('/api/marketplace/bookings',headers=m).json()[0]['state']=='expired'
    b=create_booking(cfg,m);bid=b['id'];assert c.post('/api/marketplace/driver/bookings/'+bid+'/accept',headers=cfg['driver']).status_code==200
    assert c.post('/api/marketplace/bookings/'+bid+'/cancel',headers=m).status_code==200
    with core.SessionLocal() as s:assert not mp.pickup_reserved(s,cfg['driver_id'])

@pytest.fixture
def shop_config(monkeypatch,configured):
    monkeypatch.setenv('SHOPIFY_ENABLED','true');monkeypatch.setenv('SHOPIFY_CLIENT_ID','test-client');monkeypatch.setenv('SHOPIFY_CLIENT_SECRET','test-shopify-callback-secret');monkeypatch.setenv('SHOPIFY_REDIRECT_URI','https://testserver/api/integrations/shopify/callback');monkeypatch.setenv('SHOPIFY_TOKEN_ENCRYPTION_KEY',Fernet.generate_key().decode());return configured

def signed_callback(state,shop,**extra):
    data={'state':state,'shop':shop,'code':'authorization-code-test','timestamp':str(int(core.now().timestamp())),**extra}
    data['hmac']=hmac.new(os.environ['SHOPIFY_CLIENT_SECRET'].encode(),'&'.join(f'{k}={v}' for k,v in sorted(data.items())).encode(),hashlib.sha256).hexdigest();return data

def test_shopify_callback_replay_encryption_and_store_isolation(shop_config):
    cfg=shop_config;mid,m,_=register(cfg,'shop');approve(cfg,mid);oid,other,_=register(cfg,'shop-other');approve(cfg,oid)
    assert c.post('/api/integrations/shopify/connect',headers=m,json={'shop':'https://evil.example.com'}).status_code==422
    shop='kriya-'+cfg['id'][:10]+'.myshopify.com'
    r=c.post('/api/integrations/shopify/connect',headers=m,json={'shop':shop});assert r.status_code==200,r.text
    url=r.json()['authorization_url'];assert url.startswith('https://testserver/')
    with TestClient(core.app,base_url='https://testserver') as browser:
        launch=browser.get(url,follow_redirects=False);assert launch.status_code==302,launch.text
        target=urlsplit(launch.headers['location']);assert target.hostname==shop
        state=parse_qs(target.query)['state'][0]
        payload=signed_callback(state,shop)
        assert browser.get('/api/integrations/shopify/callback',params={**payload,'hmac':'0'*64}).status_code==403
        assert c.get('/api/integrations/shopify/callback',params=payload).status_code==403 # browser-cookie binding
        with patch('app.shopify_marketplace.exchange',return_value={'access_token':'TEST_ACCESS_DO_NOT_LEAK','refresh_token':'TEST_REFRESH_DO_NOT_LEAK','expires_in':3600,'refresh_token_expires_in':7776000,'scope':'read_orders'}) as exchange:
            result=browser.get('/api/integrations/shopify/callback',params=payload);assert result.status_code==200,result.text
            assert exchange.call_args.args[1]['expiring']=='1'
            assert browser.get('/api/integrations/shopify/callback',params=payload).status_code==403
        with core.SessionLocal() as s:
            st=s.get(shopify.Store,shop);assert st.merchant_id==mid and 'TEST_ACCESS' not in st.encrypted_token and 'TEST_REFRESH' not in st.encrypted_refresh
            assert Fernet(os.environ['SHOPIFY_TOKEN_ENCRYPTION_KEY'].encode()).decrypt(st.encrypted_token.encode())==b'TEST_ACCESS_DO_NOT_LEAK'
    assert c.get('/api/integrations/shopify/stores',headers=m).json()[0]['shop']==shop
    assert c.get('/api/integrations/shopify/stores',headers=other).json()==[]
    assert c.get('/api/integrations/shopify/stores/'+shop+'/orders',headers=other).status_code==404
    assert c.post('/api/integrations/shopify/connect',headers=other,json={'shop':shop}).status_code==409
    # Mock GraphQL without a network call; no protected customer address is requested.
    import httpx
    original=httpx.Client
    def handler(request):
        assert request.url.host==shop and request.headers['X-Shopify-Access-Token']=='TEST_ACCESS_DO_NOT_LEAK'
        assert 'shippingAddress' not in json.loads(request.content)['query']
        return httpx.Response(200,json={'data':{'orders':{'nodes':[{'id':'gid://shopify/Order/123','name':'#123','createdAt':'2026-11-20T00:00:00Z','displayFulfillmentStatus':'UNFULFILLED','cancelledAt':None}], 'pageInfo':{'hasNextPage':False,'endCursor':None}}}})
    with patch('app.shopify_marketplace.httpx.Client',side_effect=lambda **kw:original(transport=httpx.MockTransport(handler))):
        r=c.post('/api/integrations/shopify/stores/'+shop+'/sync',headers=m);assert r.status_code==200,r.text;assert r.json()['synced']==1
    assert c.get('/api/integrations/shopify/stores/'+shop+'/orders',headers=m).json()[0]['booking_eligible']
    visibility(cfg)
    b=create_booking(cfg,m,booking_body(cfg,shopify_shop=shop,shopify_order_id='gid://shopify/Order/123'))
    assert b['shopify_order_id']=='gid://shopify/Order/123'
    assert c.post('/api/marketplace/bookings',headers=m,json=booking_body(cfg,shopify_shop=shop,shopify_order_id='gid://shopify/Order/123')).status_code==409
    assert c.post('/api/marketplace/bookings',headers=other,json=booking_body(cfg,shopify_shop=shop,shopify_order_id='gid://shopify/Order/123')).status_code==404
    raw=json.dumps({'admin_graphql_api_id':'gid://shopify/Order/123','name':'#123','cancelled_at':'2026-11-25T00:00:00Z'}).encode()
    header={'x-shopify-topic':'orders/cancelled','x-shopify-shop-domain':shop,'x-shopify-webhook-id':str(uuid.uuid4()),'x-shopify-hmac-sha256':'bad','content-type':'application/json'}
    assert c.post('/api/integrations/shopify/webhooks',content=raw,headers=header).status_code==401
    header['x-shopify-hmac-sha256']=base64.b64encode(hmac.new(os.environ['SHOPIFY_CLIENT_SECRET'].encode(),raw,hashlib.sha256).digest()).decode()
    assert c.post('/api/integrations/shopify/webhooks',content=raw,headers=header).status_code==200
    assert c.post('/api/integrations/shopify/webhooks',content=raw,headers=header).json()['duplicate']
    assert not c.get('/api/integrations/shopify/stores/'+shop+'/orders',headers=m).json()[0]['booking_eligible']
    assert c.post('/api/integrations/shopify/stores/'+shop+'/disconnect',headers=m).status_code==200
    with core.SessionLocal() as s:
        store=s.get(shopify.Store,shop);assert not store.encrypted_token and not store.encrypted_refresh
