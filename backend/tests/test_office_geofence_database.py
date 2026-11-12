"""Isolated database tests for the manager-controlled attendance geofence."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException
from app.main import (Base, User, OfficeGeofence, OfficeGeofenceChange,
                      OfficeGeofenceUpdate, office_attendance_policy,
                      set_office_geofence, enforce_office_punch, Punch)

@pytest.fixture
def isolated_db():
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    with Session() as session:
        manager=User(id='manager-office-test', role='manager', name='Test Manager',
                     phone='9876543210', pin_hash='test', approved=True, active=True)
        session.add(manager)
        session.commit()
        yield session, manager
    engine.dispose()

def test_saved_office_precedes_environment(monkeypatch, isolated_db):
    s, manager = isolated_db
    monkeypatch.setenv('OFFICE_GEOFENCE_ENABLED', 'true')
    monkeypatch.setenv('OFFICE_LATITUDE', '12.3')
    monkeypatch.setenv('OFFICE_LONGITUDE', '77.3')
    policy = set_office_geofence(OfficeGeofenceUpdate(
        lat=13.011568, lng=77.668173, radius_m=150,
        max_accuracy_m=75, enabled=True), s, manager)
    assert policy['source'] == 'database'
    assert policy['updated_by'] == manager.id
    assert s.query(OfficeGeofenceChange).count() == 1
    enforce_office_punch(Punch(lat=13.011568, lng=77.668173, accuracy_m=10),s)
    with pytest.raises(HTTPException) as e:
        enforce_office_punch(Punch(lat=12.3, lng=77.3, accuracy_m=10),s)
    assert e.value.status_code == 403
    with pytest.raises(HTTPException) as bad_accuracy:
        enforce_office_punch(Punch(lat=13.011568, lng=77.668173, accuracy_m=100),s)
    assert bad_accuracy.value.status_code == 422

def test_disable_database_policy_overrides_enabled_environment(monkeypatch, isolated_db):
    s, manager = isolated_db
    monkeypatch.setenv('OFFICE_GEOFENCE_ENABLED', 'true')
    saved = set_office_geofence(OfficeGeofenceUpdate(
        lat=13.0, lng=77.6, radius_m=150,
        max_accuracy_m=75, enabled=False), s, manager)
    assert saved['source'] == 'database' and saved['enabled'] is False
    enforce_office_punch(Punch(lat=0,lng=0),s)

def test_invalid_values_fail_validation():
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        OfficeGeofenceUpdate(lat=float('nan'), lng=77, radius_m=150, max_accuracy_m=75, enabled=True)
