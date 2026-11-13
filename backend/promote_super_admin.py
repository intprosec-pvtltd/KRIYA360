"""Explicit one-time production promotion. Use only after PostgreSQL backup.
Run from backend directory with DATABASE_URL configured (secret is not printed).
"""
from sqlalchemy import select
from app.main import SessionLocal,User
TARGET='intprosec2026@gmail.com'
with SessionLocal.begin() as s:
    accounts=s.scalars(select(User).where(User.email==TARGET)).all()
    if len(accounts)!=1 or accounts[0].role not in ('manager','super_admin'):
        raise SystemExit('STOP: expected exactly one existing manager account')
    u=accounts[0]
    if not u.active or not u.password_hash:raise SystemExit('STOP: account inactive or password not configured')
    if u.role=='super_admin':print('ALREADY PROMOTED; no changes')
    else:
        u.role='super_admin';print('PROMOTED existing manager account to super_admin')
