"""Regression for GPS online state and independence from punch-in state."""
import os
os.environ['DATABASE_URL']='sqlite://'
os.environ['DEMO_SEED']='true'
from datetime import datetime, timedelta, timezone
from app.main import User, gps_freshness

def test_stationary_heartbeat_is_fresh():
    time=datetime.now(timezone.utc)
    driver=User(id='test',name='Driver',phone='9876543210',role='driver',pin_hash='x',lat=12.97,lng=77.59)
    driver.last_gps=time-timedelta(minutes=7)
    driver.last_gps_received_at=time-timedelta(seconds=5)
    age,status=gps_freshness(driver,time)
    assert status=='fresh' and age==5

def test_stale_device_remains_offline_despite_shift():
    time=datetime.now(timezone.utc)
    driver=User(id='test',name='Driver',phone='9876543210',role='driver',pin_hash='x',lat=12.97,lng=77.59)
    driver.shift_start=time-timedelta(hours=1)
    driver.shift_end=None
    driver.last_gps=time-timedelta(minutes=5)
    driver.last_gps_received_at=time-timedelta(minutes=5)
    _,status=gps_freshness(driver,time)
    assert status=='offline'
    assert driver.shift_start is not None and driver.shift_end is None
