"""Regression: successful provider search must not fall through to Nominatim."""
import os
from unittest.mock import AsyncMock, patch
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
from fastapi.testclient import TestClient
from app.main import app, _geocode_cache

def test_geoapify_success_does_not_call_nominatim():
    from app.main import SessionLocal, User, hash_pin
    with SessionLocal() as db:
        user=db.get(User,'manager-demo')
        assert user is not None
        user.pin_hash=hash_pin('1234')
        db.commit()
    client=TestClient(app)
    login=client.post('/api/auth/admin/login',json={'email':'test@example.com','password':'1234'})
    # Current demo manager may be phone+PIN only; use setup-independent manager bearer token.
    from app.main import token
    with SessionLocal() as db:
        manager=db.get(User,'manager-demo')
        header={'Authorization':'Bearer '+token(manager)}
    class FakeResponse:
        def raise_for_status(self):pass
        def json(self):return {'results':[{'lat':12.9,'lon':77.6,'formatted':'Example Building'}]}
    calls=[]
    async def fake_get(self,url,*a,**kw):
        calls.append(url)
        assert 'nominatim' not in url
        return FakeResponse()
    with patch.dict(os.environ,{'GEOAPIFY_API_KEY':'test-key'}),patch('httpx.AsyncClient.get',new=fake_get):
        _geocode_cache.clear()
        response=client.get('/api/geocode/search?q=Example+Building',headers=header)
    assert response.status_code==200,response.text
    assert response.json()['results']
    assert len(calls)==2
