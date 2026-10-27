from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

import app.api.auth as auth_api
import app.api.jobs as jobs_api
import app.api.resumes as resumes_api
import app.auth as auth
from app.database.db import Base
from app.database.tables import Candidate


@pytest.fixture
def pairing_client(monkeypatch):
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

    monkeypatch.setattr(auth, 'session', session)
    monkeypatch.setattr(auth_api, 'session', session)
    monkeypatch.setattr(jobs_api, 'session', session)
    monkeypatch.setattr(resumes_api, 'session', session)
    monkeypatch.delenv('BOOTSTRAP_ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('ALLOWED_EMAIL_DOMAINS', raising=False)

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware, secret_key='test-secret')
    test_app.include_router(auth_api.router)
    test_app.include_router(resumes_api.router)
    test_app.include_router(jobs_api.router)

    with TestClient(test_app) as client:
        assert client.post('/api/auth/signup', json={
            'name': 'Recruiter',
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        }).status_code == 200
        assert client.post('/api/auth/login', json={
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        }).status_code == 200
        yield client, test_session, engine

    engine.dispose()


def test_multiple_job_descriptions_can_be_uploaded_and_selected(pairing_client, monkeypatch):
    client, test_session, _ = pairing_client
    response = client.post('/api/jobs/descriptions/upload', files=[
        ('files', ('Backend Engineer.txt', b'Backend Engineer\nRequires 5+ years of Python experience.', 'text/plain')),
        ('files', ('Ignore.md', b'Unsupported file', 'text/markdown')),
    ])

    assert response.status_code == 200
    results = response.json()['items']
    assert results[0]['ok'] is True
    assert results[0]['title'] == 'Backend Engineer'
    assert results[0]['experience'] == '5+ years'
    assert results[1]['ok'] is False
    assert results[1]['file'] == 'Ignore.md'

    with test_session() as db_session:
        recruiter = db_session.query(auth_api.User).filter_by(email='recruiter@example.com').one()
        candidate = Candidate(
            name='Ada Lovelace',
            profile={
                'candidate_name': 'Ada Lovelace',
                'total_experience_years': 6,
                'current_role': 'Python Engineer',
                'technical_skills': [],
            },
            original_filename='ada.pdf',
            uploaded_by=recruiter.id,
        )
        db_session.add(candidate)
        db_session.flush()
        candidate_id = candidate.id
        db_session.commit()

    listed = client.get('/api/jobs/descriptions')
    assert listed.status_code == 200
    job_description_id = listed.json()[0]['id']
    candidates = client.get('/api/resumes')
    assert candidates.status_code == 200
    assert candidates.json()[0]['name'] == 'Ada Lovelace'
    assert candidates.json()[0]['experience'] == 6

    seen = {}

    def analyze_job(description):
        seen['description'] = description
        return SimpleNamespace(model_dump=lambda: {
            'title': 'Backend Engineer',
            'minimum_experience_years': 5,
            'required_skills': ['Python'],
            'preferred_skills': [],
        })

    def analyze_match(profile, job, description):
        seen['profile'] = profile
        return SimpleNamespace(model_dump=lambda: {})

    monkeypatch.setattr(jobs_api, 'analyze_job_with_gemini', analyze_job)
    monkeypatch.setattr(jobs_api, 'analyze_semantic_match', analyze_match)
    monkeypatch.setattr(jobs_api, 'score_match', lambda *args: {'score': 92})
    monkeypatch.setattr(jobs_api, 'save_analysis', lambda *args: {'id': 'saved-match'})

    matched = client.post('/api/jobs/match-saved', json={
        'candidate_id': candidate_id,
        'job_description_id': job_description_id,
    })
    assert matched.status_code == 200, matched.text
    data = matched.json()
    assert data['candidate']['name'] == 'Ada Lovelace'
    assert data['candidate']['experience'] == 6
    assert data['selected_job_description']['title'] == 'Backend Engineer'
    assert data['selected_job_description']['experience'] == '5+ years'
    assert 'Job title: Backend Engineer' in seen['description']
    assert 'Required experience: 5+ years' in seen['description']
    assert seen['profile']['candidate_name'] == 'Ada Lovelace'


def test_manual_job_description_requires_title_and_text(pairing_client):
    client, _, _ = pairing_client
    response = client.post('/api/jobs/descriptions', json={
        'title': '',
        'description': 'A job description',
    })
    assert response.status_code == 400
    assert response.json()['detail'] == 'Enter a job title.'


def test_duplicate_job_descriptions_are_not_saved(pairing_client):
    client, test_session, _ = pairing_client
    content = 'Senior Backend Engineer\nRequires Python and PostgreSQL experience.'
    first = client.post('/api/jobs/descriptions', json={
        'title': 'Senior Backend Engineer',
        'description': content,
    })
    duplicate = client.post('/api/jobs/descriptions', json={
        'title': 'Another title',
        'description': '  senior backend engineer\n\nREQUIRES Python and PostgreSQL experience. ',
    })

    assert first.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()['duplicate'] is True
    assert duplicate.json()['id'] == first.json()['id']

    uploaded = client.post('/api/jobs/descriptions/upload', files=[
        ('files', ('same-content.txt', content.encode(), 'text/plain')),
    ])
    assert uploaded.status_code == 200
    assert uploaded.json()['items'][0]['duplicate'] is True

    with test_session() as db_session:
        assert db_session.query(jobs_api.JobDescription).count() == 1
