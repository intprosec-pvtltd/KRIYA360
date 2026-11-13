"""Role authorisation tests without touching persistent database rows."""
import pytest
from fastapi import HTTPException
from app.main import super_admin,manager
class FakeUser:
 def __init__(self,role):self.role=role

def test_only_super_admin_can_change_policy():
    assert super_admin(FakeUser('super_admin')).role=='super_admin'
    with pytest.raises(HTTPException) as ex:super_admin(FakeUser('manager'))
    assert ex.value.status_code==403

def test_management_access_for_both():
    assert manager(FakeUser('manager')).role=='manager'
    assert manager(FakeUser('super_admin')).role=='super_admin'
    with pytest.raises(HTTPException):manager(FakeUser('driver'))
