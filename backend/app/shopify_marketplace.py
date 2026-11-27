"""Standalone Shopify store connection (NOT universal Shopify SSO).

Merchant authenticates with KRIYA360 first. Shopify authorizes a particular shop.
Tokens stay in the backend, encrypted at rest. Read-only order summaries; never
fulfill or charge an order without a separately implemented authorized workflow.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
from datetime import timedelta
from urllib.parse import urlencode, urlsplit
from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, UniqueConstraint, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet, InvalidToken
import httpx
from . import main as core
from . import marketplace as mp

router=APIRouter(prefix='/api/integrations/shopify',tags=['Shopify merchant integration'])
SHOP=re.compile(r'^[a-z0-9][a-z0-9-]{0,62}\.myshopify\.com$')
OID=re.compile(r'^gid://shopify/Order/[0-9]+$')

class Store(core.Base):
    __tablename__='marketplace_shopify_stores'
    shop=Column(String(160),primary_key=True)
    merchant_id=Column(String,ForeignKey('marketplace_merchants.id'),nullable=False,index=True)
    encrypted_token=Column(Text,nullable=False,default='')
    encrypted_refresh=Column(Text,nullable=False,default='')
    token_expires_at=Column(DateTime(timezone=True))
    refresh_expires_at=Column(DateTime(timezone=True))
    scope=Column(String,nullable=False,default='')
    state=Column(String,nullable=False,default='connected')
    connected_at=Column(DateTime(timezone=True),nullable=False)
    synced_at=Column(DateTime(timezone=True))

class OAuthState(core.Base):
    __tablename__='marketplace_shopify_oauth'
    state_hash=Column(String(64),primary_key=True)
    merchant_id=Column(String,ForeignKey('marketplace_merchants.id'),nullable=False)
    shop=Column(String(160),nullable=False)
    expires_at=Column(DateTime(timezone=True),nullable=False)
    browser_hash=Column(String(64),nullable=False,default='')
    consumed=Column(Boolean,default=False,nullable=False)

class Order(core.Base):
    __tablename__='marketplace_shopify_orders'
    __table_args__=(UniqueConstraint('shop','order_id',name='uq_marketplace_shopify_order'),)
    key=Column(String(64),primary_key=True)
    shop=Column(String(160),ForeignKey('marketplace_shopify_stores.shop'),nullable=False,index=True)
    order_id=Column(String(160),nullable=False)
    name=Column(String(160),nullable=False)
    created=Column(String(60),nullable=False,default='')
    fulfillment=Column(String(60),nullable=False,default='')
    cancelled=Column(Boolean,nullable=False,default=False)
    updated_at=Column(DateTime(timezone=True),nullable=False)

class Webhook(core.Base):
    __tablename__='marketplace_shopify_webhooks'
    key=Column(String(64),primary_key=True)
    created_at=Column(DateTime(timezone=True),nullable=False)

class Connect(BaseModel):
    shop:str=Field(min_length=3,max_length=160)


def digest(value):return hashlib.sha256(value.encode()).hexdigest()

def normalize_shop(value):
    shop=value.strip().lower()
    if not SHOP.fullmatch(shop):core.err(422,'Enter the original shop-name.myshopify.com domain')
    return shop

def settings():
    mp.feature()
    if os.getenv('SHOPIFY_ENABLED','false').lower()!='true':core.err(503,'Shopify connection is not configured yet')
    cid=os.getenv('SHOPIFY_CLIENT_ID','').strip();sec=os.getenv('SHOPIFY_CLIENT_SECRET','').strip();redirect=os.getenv('SHOPIFY_REDIRECT_URI','').strip();version=os.getenv('SHOPIFY_API_VERSION','2026-10').strip()
    u=urlsplit(redirect)
    if not cid or not sec or u.scheme!='https' or not u.hostname or u.username or u.password or u.path!='/api/integrations/shopify/callback' or u.query or u.fragment or not re.fullmatch(r'20\d{2}-(01|04|07|10)',version):core.err(503,'Shopify configuration is incomplete')
    try:cipher=Fernet(os.environ['SHOPIFY_TOKEN_ENCRYPTION_KEY'].encode())
    except (KeyError,ValueError):core.err(503,'Shopify token encryption is not configured')
    return cid,sec,redirect,version,cipher

@router.get('/status')
def status(m=Depends(mp.approved)):
    return {'enabled':os.getenv('SHOPIFY_ENABLED','false').lower()=='true','authentication':'merchant_account_linking','scope':'read_orders','fulfillment_writeback':False}

@router.post('/connect')
def connect(x:Connect,m=Depends(mp.approved),s:Session=Depends(core.db)):
    cid,sec,redirect,version,cipher=settings();shop=normalize_shop(x.shop)
    mp.rate(s,'shop-connect:'+m.id,8,3600)
    existing=s.get(Store,shop)
    if existing and existing.merchant_id!=m.id:core.err(409,'Store is already linked. Contact management.')
    state=secrets.token_urlsafe(32)
    s.add(OAuthState(state_hash=digest(state),merchant_id=m.id,shop=shop,expires_at=core.now()+timedelta(minutes=10)))
    s.commit()
    # Open this one-time URL in the external browser; it binds the callback to a browser cookie.
    base=redirect.removesuffix('/callback')
    return {'authorization_url':base+'/authorize?'+urlencode({'state':state})}

@router.get('/authorize')
def authorize(state:str,s:Session=Depends(core.db)):
    cid,sec,redirect,version,cipher=settings()
    if len(state)>128:core.err(400,'Invalid authorization state')
    row=s.scalar(select(OAuthState).where(OAuthState.state_hash==digest(state)).with_for_update())
    if not row or row.consumed or row.browser_hash or core.naive(row.expires_at)<=core.naive(core.now()):core.err(400,'Authorization request expired. Return to KRIYA360.')
    m=s.get(mp.Merchant,row.merchant_id)
    if not m or m.state!='approved':core.err(403,'Merchant approval required')
    cookie=secrets.token_urlsafe(32);row.browser_hash=digest(cookie);s.commit()
    url='https://'+normalize_shop(row.shop)+'/admin/oauth/authorize?'+urlencode({'client_id':cid,'scope':'read_orders','redirect_uri':redirect,'state':state})
    response=RedirectResponse(url,status_code=302,headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    response.set_cookie('kriya_shopify_state',cookie,max_age=600,secure=True,httponly=True,samesite='lax',path='/api/integrations/shopify/callback')
    return response


def verify_callback(request,client_secret):
    pairs=list(request.query_params.multi_items())
    if len(pairs)>20 or len({k for k,v in pairs})!=len(pairs):core.err(400,'Invalid authorization callback')
    params=dict(pairs);received=params.pop('hmac','')
    if not re.fullmatch(r'[0-9a-f]{64}',received):core.err(403,'Invalid Shopify signature')
    message='&'.join(f'{k}={v}' for k,v in sorted(params.items()))
    expected=hmac.new(client_secret.encode(),message.encode(),hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected,received):core.err(403,'Invalid Shopify signature')
    try:stamp=int(params.get('timestamp',''))
    except ValueError:core.err(400,'Invalid Shopify timestamp')
    if abs(core.now().timestamp()-stamp)>600:core.err(400,'Authorization callback expired')
    return params


def exchange(shop,data,cid,sec):
    try:
        with httpx.Client(timeout=20,follow_redirects=False) as client:
            r=client.post('https://'+normalize_shop(shop)+'/admin/oauth/access_token',data={'client_id':cid,'client_secret':sec,**data},headers={'Accept':'application/json'})
            r.raise_for_status();payload=r.json()
    except (httpx.HTTPError,ValueError):core.err(502,'Shopify authorization or token refresh failed. Reconnect the store if necessary.')
    if not isinstance(payload,dict):core.err(502,'Shopify returned an invalid authorization response')
    return payload


def set_tokens(store,payload,cipher):
    # Require the expiring offline tokens mandatory for new public apps.
    try:
        token=payload['access_token'];refresh=payload['refresh_token'];seconds=int(payload['expires_in']);refresh_seconds=int(payload['refresh_token_expires_in'])
        scope=payload.get('scope',store.scope or '')
        if not isinstance(token,str) or not token or not isinstance(refresh,str) or not refresh or seconds<=0 or refresh_seconds<=0 or 'read_orders' not in scope.split(','):raise ValueError()
    except (KeyError,TypeError,ValueError,AttributeError):core.err(502,'Shopify did not grant the required expiring order access')
    store.encrypted_token=cipher.encrypt(token.encode()).decode();store.encrypted_refresh=cipher.encrypt(refresh.encode()).decode();store.token_expires_at=core.now()+timedelta(seconds=seconds);store.refresh_expires_at=core.now()+timedelta(seconds=refresh_seconds);store.scope=scope;store.state='connected'

@router.get('/callback',response_class=PlainTextResponse)
def callback(request:Request,s:Session=Depends(core.db)):
    cid,sec,redirect,version,cipher=settings();params=verify_callback(request,sec)
    shop=normalize_shop(params.get('shop',''));state=params.get('state','');code=params.get('code','');cookie=request.cookies.get('kriya_shopify_state','')
    if not state or len(state)>128 or not code or len(code)>1024 or not cookie:core.err(403,'Authorization state missing. Reconnect from KRIYA360.')
    row=s.scalar(select(OAuthState).where(OAuthState.state_hash==digest(state)).with_for_update())
    if not row or row.consumed or row.shop!=shop or not row.browser_hash or not hmac.compare_digest(row.browser_hash,digest(cookie)) or core.naive(row.expires_at)<=core.naive(core.now()):core.err(403,'Authorization state invalid or expired')
    merchant_id=row.merchant_id
    m=s.scalar(select(mp.Merchant).where(mp.Merchant.id==merchant_id).with_for_update())
    if not m or m.state!='approved':core.err(403,'Merchant approval required')
    store=s.scalar(select(Store).where(Store.shop==shop).with_for_update())
    if store and store.merchant_id!=merchant_id:core.err(409,'Store is already linked to another account')
    # Reserve the shop before exchanging a code. PostgreSQL row/unique locks
    # serialize token rotation for this installation; no cross-tenant overwrites.
    row.consumed=True
    new_store=store is None
    if new_store:
        store=Store(shop=shop,merchant_id=merchant_id,connected_at=core.now(),state='connecting');s.add(store)
        try:s.flush()
        except IntegrityError:s.rollback();core.err(409,'Store authorization conflict. Retry from KRIYA360.')
    from fastapi import HTTPException
    try:
        payload=exchange(shop,{'code':code,'expiring':'1'},cid,sec)
        set_tokens(store,payload,cipher)
    except HTTPException:
        if new_store:s.delete(store)
        s.commit()  # consume failed callback; the merchant can initiate a fresh link
        raise
    mp.audit(s,merchant_id,'shopify_connected',shop)
    try:s.commit()
    except IntegrityError:s.rollback();core.err(409,'Store connection conflict. Contact management.')
    response=PlainTextResponse('Shopify store connected. Return to KRIYA360 and refresh the Stores page.',headers={'Cache-Control':'no-store','Referrer-Policy':'no-referrer'})
    response.delete_cookie('kriya_shopify_state',path='/api/integrations/shopify/callback',secure=True,httponly=True,samesite='lax');return response


def store_view(st):return {'shop':st.shop,'state':st.state,'scope':st.scope,'connected_at':core.iso(st.connected_at),'synced_at':core.iso(st.synced_at)}
@router.get('/stores')
def stores(m=Depends(mp.approved),s:Session=Depends(core.db)):
    return [store_view(st) for st in s.scalars(select(Store).where(Store.merchant_id==m.id).limit(100))]

def owned_store(s,m,shop,lock=False):
    q=select(Store).where(Store.shop==normalize_shop(shop),Store.merchant_id==m.id)
    if lock:q=q.with_for_update()
    st=s.scalar(q)
    if not st:core.err(404,'Shopify store not found')
    return st

@router.post('/stores/{shop}/disconnect')
def disconnect(shop:str,m=Depends(mp.approved),s:Session=Depends(core.db)):
    st=owned_store(s,m,shop,True);st.encrypted_token='';st.encrypted_refresh='';st.state='disconnected'
    mp.audit(s,m.id,'shopify_disconnected',st.shop);s.commit()
    return {'state':'disconnected','notice':'Local credentials removed. Uninstall KRIYA360 in Shopify to revoke the app installation.'}


def token_for(st,cid,sec,cipher,s):
    if st.state!='connected' or not st.encrypted_token or not st.encrypted_refresh:core.err(409,'Reconnect the Shopify store')
    try:
        if st.token_expires_at and core.naive(st.token_expires_at)>core.naive(core.now()+timedelta(minutes=5)):
            return cipher.decrypt(st.encrypted_token.encode()).decode()
        if not st.refresh_expires_at or core.naive(st.refresh_expires_at)<=core.naive(core.now()):core.err(409,'Shopify access expired. Reconnect the store.')
        refresh=cipher.decrypt(st.encrypted_refresh.encode()).decode()
    except (InvalidToken,ValueError):core.err(409,'Stored Shopify credentials unavailable. Reconnect the store.')
    payload=exchange(st.shop,{'grant_type':'refresh_token','refresh_token':refresh},cid,sec)
    set_tokens(st,payload,cipher);s.flush()
    # Commit the rotating refresh token before the next external request.
    token=cipher.decrypt(st.encrypted_token.encode()).decode();s.commit();return token

QUERY='query KriyaOrders($after: String) { orders(first: 50, after: $after, sortKey: UPDATED_AT, reverse: true) { nodes { id name createdAt cancelledAt displayFulfillmentStatus } pageInfo { hasNextPage endCursor } } }'

def put_order(s,shop,oid,name,created,fulfillment,cancelled):
    if not isinstance(oid,str) or not OID.fullmatch(oid):return
    key=digest(shop+'|'+oid)
    row=s.scalar(select(Order).where(Order.key==key).with_for_update())
    if not row:row=Order(key=key,shop=shop,order_id=oid);s.add(row)
    raw=str(fulfillment or '').upper();mapped={'PARTIAL':'PARTIALLY_FULFILLED','NULL':'UNFULFILLED'}.get(raw,raw)
    row.name=str(name or oid)[-160:];row.created=str(created or '')[:60];row.fulfillment=mapped[:60];row.cancelled=bool(row.cancelled or cancelled);row.updated_at=core.now()
    if row.cancelled:
        for booking in s.scalars(select(mp.Booking).where(mp.Booking.shopify_shop==shop,mp.Booking.shopify_order_id==oid,mp.Booking.state.in_(['requested','accepted','arrived','collected']))):
            if booking.state=='requested':booking.state='cancelled'
            elif mp.booking_state(s,booking)!='completed':booking.problem='Shopify order cancelled. Contact merchant and management before proceeding.'

@router.post('/stores/{shop}/sync')
def sync_orders(shop:str,m=Depends(mp.approved),s:Session=Depends(core.db)):
    cid,sec,redirect,version,cipher=settings();mp.rate(s,'shop-sync:'+m.id,10,600)
    st=owned_store(s,m,shop,True);token=token_for(st,cid,sec,cipher,s);shop=st.shop
    # Bounded on-demand import: order identifiers/status only, no protected shipping PII.
    cursor=None;count=0;pages=0;has_more=False
    try:
        with httpx.Client(timeout=20,follow_redirects=False) as client:
            for _ in range(10):
                response=client.post(f'https://{shop}/admin/api/{version}/graphql.json',headers={'X-Shopify-Access-Token':token,'Content-Type':'application/json'},json={'query':QUERY,'variables':{'after':cursor}})
                response.raise_for_status();body=response.json()
                if body.get('errors'):core.err(502,'Shopify order access rejected. Check granted scopes.')
                result=body['data']['orders'];nodes=result['nodes'];page=result['pageInfo'];pages+=1
                current=owned_store(s,m,shop,True)
                if current.state!='connected':core.err(409,'Store disconnected during synchronization')
                for order in nodes:
                    put_order(s,shop,order['id'],order['name'],order['createdAt'],order['displayFulfillmentStatus'],order.get('cancelledAt'));count+=1
                current.synced_at=core.now();s.commit()
                has_more=bool(page['hasNextPage']);cursor=page.get('endCursor')
                if not has_more:break
                if not cursor:core.err(502,'Shopify pagination failed')
    except (httpx.HTTPError,ValueError,KeyError,TypeError):s.rollback();core.err(502,'Shopify synchronization interrupted. Retry safely.')
    return {'synced':count,'pages':pages,'more_orders_available':has_more,'mode':'read_only_order_summaries'}

@router.get('/stores/{shop}/orders')
def orders(shop:str,m=Depends(mp.approved),s:Session=Depends(core.db)):
    st=owned_store(s,m,shop)
    if st.state!='connected':core.err(409,'Reconnect the store')
    return [{'id':o.order_id,'shop':o.shop,'name':o.name,'created_at':o.created,'fulfillment_status':o.fulfillment,'cancelled':o.cancelled,'booking_eligible':not o.cancelled and o.fulfillment in ('UNFULFILLED','PARTIALLY_FULFILLED','UNSHIPPED')} for o in s.scalars(select(Order).where(Order.shop==st.shop).order_by(Order.created.desc()).limit(500))]


def validate_order_reference(s,m,shop,oid):
    if not shop or not oid or not OID.fullmatch(oid):core.err(422,'Select a synchronized Shopify order')
    st=owned_store(s,m,shop)
    if st.state!='connected':core.err(409,'Reconnect the Shopify store')
    row=s.scalar(select(Order).where(Order.key==digest(st.shop+'|'+oid)).with_for_update())
    if not row or row.cancelled or row.fulfillment not in ('UNFULFILLED','PARTIALLY_FULFILLED','UNSHIPPED'):core.err(409,'Shopify order is not eligible for a delivery request')
    for b in s.scalars(select(mp.Booking).where(mp.Booking.merchant_id==m.id,mp.Booking.shopify_shop==st.shop,mp.Booking.shopify_order_id==oid)):
        if mp.booking_state(s,b) not in ('cancelled','rejected','expired'):core.err(409,'A delivery already exists for this Shopify order')

@router.post('/webhooks')
async def webhooks(request:Request,s:Session=Depends(core.db)):
    # Signed notifications can be wired in the Shopify Dev Dashboard. We do not
    # treat an incoming webhook as identity authentication or fulfillment proof.
    secret=os.getenv('SHOPIFY_CLIENT_SECRET','')
    if not secret:core.err(503,'Shopify is not configured')
    data=bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data)>2*1024*1024:core.err(413,'Webhook too large')
    expected=base64.b64encode(hmac.new(secret.encode(),bytes(data),hashlib.sha256).digest()).decode()
    if not hmac.compare_digest(expected,request.headers.get('x-shopify-hmac-sha256','')):core.err(401,'Invalid webhook signature')
    shop=normalize_shop(request.headers.get('x-shopify-shop-domain',''));topic=request.headers.get('x-shopify-topic','');event_id=request.headers.get('x-shopify-webhook-id','')
    if not event_id or len(event_id)>160:core.err(400,'Webhook ID missing')
    key=digest(shop+'|'+event_id)
    if s.get(Webhook,key):return {'ok':True,'duplicate':True}
    st=s.scalar(select(Store).where(Store.shop==shop).with_for_update())
    if not st:return {'ok':True}
    if topic=='app/uninstalled':st.state='uninstalled';st.encrypted_token='';st.encrypted_refresh=''
    elif topic in ('orders/create','orders/updated','orders/cancelled'):
        if st.state!='connected':return {'ok':True}
        try:body=json.loads(data)
        except ValueError:core.err(400,'Invalid webhook payload')
        if not isinstance(body,dict):core.err(400,'Invalid webhook payload')
        oid=body.get('admin_graphql_api_id','');state=body.get('fulfillment_status') or 'UNFULFILLED'
        put_order(s,shop,oid,body.get('name'),body.get('created_at'),state,body.get('cancelled_at') or topic=='orders/cancelled')
    else:core.err(400,'Unsupported webhook topic')
    s.add(Webhook(key=key,created_at=core.now()))
    try:s.commit()
    except IntegrityError:s.rollback();return {'ok':True,'duplicate':True}
    return {'ok':True}


def require_active_order(s,booking):
    if not booking.shopify_order_id:return
    st=s.get(Store,booking.shopify_shop);row=s.get(Order,digest(booking.shopify_shop+'|'+booking.shopify_order_id))
    if not st or st.state!='connected' or st.merchant_id!=booking.merchant_id or not row or row.cancelled or row.fulfillment not in ('UNFULFILLED','PARTIALLY_FULFILLED','UNSHIPPED'):
        core.err(409,'Shopify order is no longer eligible. Contact merchant and management.')
