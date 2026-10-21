from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

import app.api.auth as auth_api
from app.database.db import Base
from app.database.tables import User


def test_signup_creates_active_account_that_can_sign_in(monkeypatch):
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session():
        db_session = test_session()
        try:
            yield db_session
            db_session.commit()
        except Exception:
            db_session.rollback()
            raise
        finally:
            db_session.close()

    monkeypatch.setattr(auth_api, 'session', session)
    monkeypatch.delenv('BOOTSTRAP_ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('ALLOWED_EMAIL_DOMAINS', raising=False)

    app = FastAPI()
    app.add_middleware(SessionMiddleware, secret_key='test-secret')
    app.include_router(auth_api.router)

    with TestClient(app) as client:
        signup = client.post('/api/auth/signup', json={
            'name': 'Recruiter',
            'email': 'RECRUITER@example.com',
            'password': 'long-enough-password',
        })

        assert signup.status_code == 200
        assert signup.json() == {
            'created': True,
            'message': 'Account created. You can sign in now.',
        }
        with test_session() as db_session:
            user = db_session.scalar(select(User).where(User.email == 'recruiter@example.com'))
            assert user is not None
            assert user.role == 'recruiter'
            assert user.is_active is True

        login = client.post('/api/auth/login', json={
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        })
        assert login.status_code == 200
        assert login.json()['email'] == 'recruiter@example.com'

        duplicate = client.post('/api/auth/signup', json={
            'name': 'Recruiter',
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        })
        assert duplicate.status_code == 409

    engine.dispose()
