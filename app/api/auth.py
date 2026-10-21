import os
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import (admin_only, audit, current_user, hash_password,
                      rate_limit, verify_password)
from app.database.db import session
from app.database.tables import AuditLog, User

router = APIRouter(tags=['auth'])
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


class SignUp(BaseModel):
    name: str
    email: str
    password: str


class Login(BaseModel):
    email: str
    password: str


class RoleChange(BaseModel):
    role: str


def _allowed_domains():
    return [d.strip().lower() for d in os.getenv('ALLOWED_EMAIL_DOMAINS', '').split(',') if d.strip()]


@router.post('/api/auth/signup')
def signup(req: SignUp, request: Request):
    rate_limit(request, 'signup', limit=10)
    email = req.email.strip().lower()
    name = req.name.strip()
    if not name:
        raise HTTPException(400, 'Enter your full name.')
    if not EMAIL_RE.match(email):
        raise HTTPException(400, 'Enter a valid email address.')
    if len(req.password) < 10:
        raise HTTPException(400, 'Use at least 10 characters for your password.')
    domains = _allowed_domains()
    if domains and email.rsplit('@', 1)[-1] not in domains:
        raise HTTPException(400, 'Sign-up is limited to these email domains: ' + ', '.join(domains) + '.')

    bootstrap = os.getenv('BOOTSTRAP_ADMIN_EMAIL', '').strip().lower()
    with session() as s:
        if s.scalar(select(User).where(User.email == email)):
            raise HTTPException(409, 'An account with this email already exists. Please sign in.')
        no_admin_yet = s.scalar(select(User.id).where(User.role == 'admin')) is None
        first_admin = bool(bootstrap) and email == bootstrap and no_admin_yet
        s.add(User(email=email, name=name, password_hash=hash_password(req.password),
                   role='admin' if first_admin else 'recruiter', is_active=True))
        s.add(AuditLog(user_id='', action='signup', detail=email))
    message = 'Administrator account created. You can sign in now.' if first_admin else \
        'Account created. You can sign in now.'
    return {'created': True, 'message': message}


@router.post('/api/auth/login')
def login(req: Login, request: Request):
    rate_limit(request, 'login', limit=10)
    with session() as s:
        u = s.scalar(select(User).where(User.email == req.email.strip().lower()))
        if not u or not verify_password(req.password, u.password_hash):
            raise HTTPException(401, 'Incorrect email or password.')
        if not u.is_active:
            raise HTTPException(403, 'This account is disabled. Contact an administrator.')
        request.session.clear()
        request.session['user_id'] = u.id
        return {'email': u.email, 'name': u.name, 'role': u.role}


@router.post('/api/auth/logout')
def logout(request: Request):
    request.session.clear()
    return {'ok': True}


@router.get('/api/auth/me')
def whoami(user: dict = Depends(current_user)):
    return user


@router.get('/api/users')
def list_users(_: dict = Depends(admin_only)):
    with session() as s:
        rows = s.scalars(select(User).order_by(User.created_at.desc())).all()
        return [{'id': u.id, 'name': u.name, 'email': u.email, 'role': u.role,
                 'is_active': u.is_active, 'created_at': u.created_at.isoformat()} for u in rows]


def _target(s, user_id):
    u = s.get(User, user_id)
    if not u:
        raise HTTPException(404, 'User not found.')
    return u


@router.post('/api/users/{user_id}/enable')
def enable(user_id: str, admin: dict = Depends(admin_only)):
    with session() as s:
        u = _target(s, user_id)
        u.is_active = True
        email = u.email
    audit(admin, 'user_enable', email)
    return {'ok': True}


@router.post('/api/users/{user_id}/disable')
def disable(user_id: str, admin: dict = Depends(admin_only)):
    if user_id == admin['id']:
        raise HTTPException(400, 'You cannot disable your own account.')
    with session() as s:
        u = _target(s, user_id)
        u.is_active = False
        email = u.email
    audit(admin, 'user_disable', email)
    return {'ok': True}


@router.post('/api/users/{user_id}/role')
def change_role(user_id: str, req: RoleChange, admin: dict = Depends(admin_only)):
    if req.role not in {'admin', 'recruiter'}:
        raise HTTPException(400, 'Role must be admin or recruiter.')
    if user_id == admin['id']:
        raise HTTPException(400, 'You cannot change your own role.')
    with session() as s:
        u = _target(s, user_id)
        u.role = req.role
        email = u.email
    audit(admin, 'user_role_' + req.role, email)
    return {'ok': True}
