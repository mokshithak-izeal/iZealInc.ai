import hashlib
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session as SQLAlchemySession

from app.database.db import session
from app.database.tables import AuditLog, User, UserSession

SESSION_TTL_SECONDS = 60 * 60 * 8
_SESSION_ACTIVITY_UPDATE_SECONDS = 5 * 60


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def create_auth_session(db_session: SQLAlchemySession, user_id: str, request: Request) -> str:
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    db_session.add(UserSession(
        user_id=user_id,
        token_hash=session_token_hash(token),
        user_agent=request.headers.get('user-agent', '')[:512],
        ip_address=(request.client.host if request.client else '')[:45],
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(seconds=SESSION_TTL_SECONDS),
    ))
    return token


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], hashed.encode())
    except ValueError:
        return False


def session_user(request: Request):
    """Return the signed-in user as a dict, or None."""
    token = request.session.get('session_token')
    if not isinstance(token, str):
        request.session.clear()
        return None
    with session() as s:
        auth_session = s.scalar(select(UserSession).where(
            UserSession.token_hash == session_token_hash(token),
            UserSession.revoked_at.is_(None),
        ))
        now = datetime.now(timezone.utc)
        if not auth_session or _as_utc(auth_session.expires_at) <= now:
            request.session.clear()
            return None
        u = s.get(User, auth_session.user_id)
        if u and u.is_active:
            last_seen = _as_utc(auth_session.last_seen_at)
            if (now - last_seen).total_seconds() >= _SESSION_ACTIVITY_UPDATE_SECONDS:
                auth_session.last_seen_at = now
            return {'id': u.id, 'email': u.email, 'name': u.name, 'role': u.role}
        auth_session.revoked_at = now
        request.session.clear()
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
