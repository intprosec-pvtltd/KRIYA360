"""Offline contract tests for the opt-in Google Maps adapter."""
import asyncio
import importlib
import os
from unittest.mock import patch
import httpx


def app_module():
 return importlib.import_module('app.main')


def test_polyline_is_longitude_latitude():
 m=app_module()
 assert m.google_decode_polyline('_p~iF~ps|U_ulLnnqC_mqNvxq`@')==[
  [-120.2,38.5],[-120.95,40.7],[-126.453,43.252]]


def test_google_routes_contract_and_shortest_choice(monkeypatch):
 m=app_module()
 monkeypatch.setenv('KRIYA_MAP_PROVIDER','google')
 monkeypatch.setenv('GOOGLE_MAPS_SERVER_API_KEY','test-only')
 poly='_p~iF~ps|U_ulLnnqC_mqNvxq`@'
 routes=[{'distanceMeters':5100,'duration':'820s','staticDuration':'700s','polyline':{'encodedPolyline':poly}},
         {'distanceMeters':4000,'duration':'980s','staticDuration':'850s','polyline':{'encodedPolyline':poly}}]
 def handler(request):
  assert request.url.path.endswith(':computeRoutes')
  assert request.headers.get('X-Goog-FieldMask')
  assert request.headers.get('X-Goog-Api-Key')=='test-only'
  return httpx.Response(200,json={'routes':routes})
 transport=httpx.MockTransport(handler)
 original=httpx.AsyncClient
 monkeypatch.setattr(m.httpx,'AsyncClient',lambda *a,**k:original(transport=transport))
 fastest=asyncio.run(m.route_options(38.5,-120.2,43.252,-126.453,'fastest'))
 shortest=asyncio.run(m.route_options(38.5,-120.2,43.252,-126.453,'shortest'))
 assert fastest['distance_km']==5.1
 assert fastest['traffic_aware'] is True
 assert fastest['source'].startswith('Google Routes')
 assert fastest['traffic_delay_min']==2
 assert shortest['distance_km']==4
 assert shortest['shortest_guaranteed'] is False
 assert len(shortest['alternative_routes'])==1


def test_google_places_contract(monkeypatch):
 m=app_module()
 monkeypatch.setenv('GOOGLE_MAPS_SERVER_API_KEY','test-only')
 def handler(request):
  assert request.url.path.endswith('places:searchText')
  assert request.headers.get('X-Goog-FieldMask')
  return httpx.Response(200,json={'places':[{'displayName':{'text':'Office'},'formattedAddress':'Bengaluru, India','location':{'latitude':12.9,'longitude':77.6}}]})
 transport=httpx.MockTransport(handler)
 original=httpx.AsyncClient
 monkeypatch.setattr(m.httpx,'AsyncClient',lambda *a,**k:original(transport=transport))
 result=asyncio.run(m.google_search_places('Office Bengaluru'))
 assert result['results'][0]=={'label':'Office, Bengaluru, India','lat':12.9,'lng':77.6,'type':'place'}


def test_google_matrix_road_eta_contract(monkeypatch):
 m=app_module()
 monkeypatch.setenv('GOOGLE_MAPS_SERVER_API_KEY','test-only')
 class Order:pickup_lat=12.97;pickup_lng=77.59
 drivers=[{'driver_id':'a','name':'A','lat':12.98,'lng':77.60,'on_shift':True,'gps_fresh':True,'queued_tasks':0,'active_task':None,'score':1,'reasons':[],'distance_to_pickup_km':1,'distance_type':'straight_line_estimate'}]
 def handler(request):
  assert request.url.path.endswith('computeRouteMatrix')
  return httpx.Response(200,json=[{'originIndex':0,'destinationIndex':0,'condition':'ROUTE_EXISTS','duration':'480s','distanceMeters':3100}])
 original=httpx.AsyncClient
 monkeypatch.setattr(m.httpx,'AsyncClient',lambda *a,**k:original(transport=httpx.MockTransport(handler)))
 ranked,traffic=asyncio.run(m.google_rank_by_drive_time(drivers,Order()))
 assert traffic is True
 assert ranked[0]['road_eta_min']==8
 assert ranked[0]['distance_to_pickup_km']==3.1
 assert ranked[0]['distance_type']=='google_traffic_aware_road'
