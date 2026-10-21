import time
from collections import defaultdict, deque

import bcrypt
from fastapi import Depends, HTTPException, Request

from app.database.db import session
from app.database.tables import AuditLog, User


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def session_user(request: Request):
    """Return the signed-in user as a dict, or None. Never raises."""
    user_id = request.session.get('user_id')
    if not user_id:
        return None
    with session() as s:
        u = s.get(User, user_id)
        if u and u.is_active:
            return {'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role}
    return None


def current_user(request: Request) -> dict:
    user = session_user(request)
    if not user:
        raise HTTPException(401, 'Please sign in.')
    return user


def admin_only(user: dict = Depends(current_user)) -> dict:
    if user['role'] != 'admin':
        raise HTTPException(403, 'Administrator access required.')
    return user


def audit(user: dict, action: str, detail: str = ''):
    with session() as s:
        s.add(AuditLog(user_id=user['id'], action=action, detail=detail))


# Simple in-memory limiter: at most `limit` attempts per `window` seconds per IP.
_attempts = defaultdict(deque)


def rate_limit(request: Request, bucket: str, limit: int = 10, window: int = 600):
    ip = request.client.host if request.client else 'unknown'
    q = _attempts[(bucket, ip)]
    now = time.time()
    while q and now - q[0] > window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, 'Too many attempts. Wait a few minutes and try again.')
    q.append(now)
