from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.database.applications as applications
from app.api.jobs import router
from app.database.db import Base


def test_marked_application_is_available_in_applications_tab(monkeypatch):
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

    monkeypatch.setattr(applications, 'session', session)
    app = FastAPI()
    app.include_router(router)

    with TestClient(app) as client:
        marked = client.post('/api/jobs/mark-applied', json={
            'title': 'Backend Engineer',
            'company': 'Example Inc.',
            'job_url': 'https://example.com/jobs/backend-engineer',
            'score': 92.5,
            'status': 'APPLIED',
        })

        assert marked.status_code == 200
        assert marked.json()['title'] == 'Backend Engineer'

        listed = client.get('/api/jobs/applications')

        assert listed.status_code == 200
        assert len(listed.json()) == 1
        assert listed.json()[0]['title'] == 'Backend Engineer'
        assert listed.json()[0]['company'] == 'Example Inc.'
        assert listed.json()[0]['status'] == 'APPLIED'
        assert listed.json()[0]['score'] == 92.5