"""Attendance classification regression tests, no shared DB mutations."""
import pytest
from fastapi import HTTPException
from app import main as m

def test_office_and_remote(monkeypatch):
    monkeypatch.setattr(m,'office_attendance_policy',lambda s: {'configured':True,'enabled':True,'lat':13.0,'lng':77.6,'radius_m':150,'max_accuracy_m':75})
    assert m.classify_attendance(m.Punch(lat=13.0,lng=77.6,accuracy_m=10),object())[0]=='office'
    kind,distance=m.classify_attendance(m.Punch(lat=13.01,lng=77.6,accuracy_m=10),object())
    assert kind=='remote' and distance>1000

def test_poor_gps_is_rejected(monkeypatch):
    monkeypatch.setattr(m,'office_attendance_policy',lambda s: {'configured':True,'enabled':True,'lat':13.0,'lng':77.6,'radius_m':150,'max_accuracy_m':75})
    with pytest.raises(HTTPException) as ex:m.classify_attendance(m.Punch(lat=13.0,lng=77.6,accuracy_m=95),object())
    assert ex.value.status_code==422

def test_unconfigured_does_not_invent_office(monkeypatch):
    monkeypatch.setattr(m,'office_attendance_policy',lambda s: {'enabled':False})
    assert m.classify_attendance(m.Punch(lat=13.0,lng=77.6),object())[0]=='unclassified'
