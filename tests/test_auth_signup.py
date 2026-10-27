from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

import app.api.auth as auth_api
import app.auth as auth
from app.database.db import Base
from app.database.tables import User, UserSession


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
    monkeypatch.setattr(auth, 'session', session)
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

        listed = client.get('/api/auth/sessions')
        assert listed.status_code == 200
        assert len(listed.json()['sessions']) == 1
        assert listed.json()['sessions'][0]['is_current'] is True

        with TestClient(app) as another_user:
            another_signup = another_user.post('/api/auth/signup', json={
                'name': 'Another Recruiter',
                'email': 'another@example.com',
                'password': 'another-long-password',
            })
            assert another_signup.status_code == 200
            assert another_user.post('/api/auth/login', json={
                'email': 'another@example.com',
                'password': 'another-long-password',
            }).status_code == 200
            foreign_revoke = another_user.delete(
                '/api/auth/sessions/' + listed.json()['sessions'][0]['id']
            )
            assert foreign_revoke.status_code == 404
            assert another_user.post('/api/auth/logout').status_code == 200

        with TestClient(app) as second_client:
            second_login = second_client.post('/api/auth/login', json={
                'email': 'recruiter@example.com',
                'password': 'long-enough-password',
            })
            assert second_login.status_code == 200
            second_sessions = second_client.get('/api/auth/sessions').json()['sessions']
            assert len(second_sessions) == 2
            second_session = next(row for row in second_sessions if row['is_current'])

            revoked = client.delete('/api/auth/sessions/' + second_session['id'])
            assert revoked.status_code == 200
            assert revoked.json() == {'ok': True, 'current': False}
            assert second_client.get('/api/auth/me').status_code == 401

        with TestClient(app) as third_client:
            assert third_client.post('/api/auth/login', json={
                'email': 'recruiter@example.com',
                'password': 'long-enough-password',
            }).status_code == 200
            revoke_others = client.post('/api/auth/sessions/revoke-others')
            assert revoke_others.status_code == 200
            assert revoke_others.json() == {'ok': True, 'revoked': 1}
            assert third_client.get('/api/auth/me').status_code == 401

        logout = client.post('/api/auth/logout')
        assert logout.status_code == 200
        assert client.get('/api/auth/me').status_code == 401
        with test_session() as db_session:
            assert db_session.query(UserSession).filter(UserSession.revoked_at.is_(None)).count() == 0

        duplicate = client.post('/api/auth/signup', json={
            'name': 'Recruiter',
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        })
        assert duplicate.status_code == 409

    engine.dispose()
