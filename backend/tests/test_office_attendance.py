"""Office geofence regression tests; no production DB or credentials required."""
import math
import pytest
from fastapi import HTTPException
from app.main import Punch, office_distance_m, office_attendance_policy, enforce_office_punch

def test_office_policy_default_disabled(monkeypatch):
    monkeypatch.delenv('OFFICE_GEOFENCE_ENABLED',raising=False)
    assert office_attendance_policy()=={'enabled':False}
    enforce_office_punch(Punch(lat=0,lng=0))

def test_office_policy_must_be_configured(monkeypatch):
    monkeypatch.setenv('OFFICE_GEOFENCE_ENABLED','true')
    monkeypatch.delenv('OFFICE_LATITUDE',raising=False)
    monkeypatch.delenv('OFFICE_LONGITUDE',raising=False)
    with pytest.raises(HTTPException) as exc:office_attendance_policy()
    assert exc.value.status_code==503

def test_office_boundary_and_accuracy(monkeypatch):
    for key,value in {'OFFICE_GEOFENCE_ENABLED':'true','OFFICE_LATITUDE':'12.9716','OFFICE_LONGITUDE':'77.5946','OFFICE_RADIUS_METERS':'150','OFFICE_MAX_GPS_ACCURACY_METERS':'75'}.items():monkeypatch.setenv(key,value)
    enforce_office_punch(Punch(lat=12.9716,lng=77.5946,accuracy_m=12))
    with pytest.raises(HTTPException) as missing:enforce_office_punch(Punch(lat=12.9716,lng=77.5946))
    assert missing.value.status_code==422
    with pytest.raises(HTTPException) as outside:enforce_office_punch(Punch(lat=12.9800,lng=77.5946,accuracy_m=10))
    assert outside.value.status_code==403
    with pytest.raises(HTTPException) as poor:enforce_office_punch(Punch(lat=12.9716,lng=77.5946,accuracy_m=100))
    assert poor.value.status_code==422
    assert office_distance_m(12.9716,77.5946,12.9716,77.5946)==0
