from contextlib import contextmanager
import json

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.middleware.sessions import SessionMiddleware

import app.api.resumes as resumes_api
import app.api.auth as auth_api
import app.auth as auth
from app.database.db import Base
from app.models.candidate import CandidateProfile, TechnicalSkill


@pytest.fixture
def client(monkeypatch):
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
    monkeypatch.setattr(resumes_api, 'session', session)
    monkeypatch.delenv('BOOTSTRAP_ADMIN_EMAIL', raising=False)
    monkeypatch.delenv('ALLOWED_EMAIL_DOMAINS', raising=False)

    test_app = FastAPI()
    test_app.add_middleware(SessionMiddleware, secret_key='test-secret')
    test_app.include_router(auth_api.router)
    test_app.include_router(resumes_api.router)

    with TestClient(test_app) as test_client:
        signup = test_client.post('/api/auth/signup', json={
            'name': 'Recruiter',
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        })
        assert signup.status_code == 200
        login = test_client.post('/api/auth/login', json={
            'email': 'recruiter@example.com',
            'password': 'long-enough-password',
        })
        assert login.status_code == 200
        yield test_client

    engine.dispose()


def test_analyze_pasted_resume_text(client, monkeypatch):
    profile = CandidateProfile(
        candidate_name='Ada Lovelace',
        total_experience_years=4,
        current_role='Python Developer',
        technical_skills=[
            TechnicalSkill(
                name='Python',
                confidence=0.98,
                evidence='Python is listed in the skills section.',
            ),
        ],
    )
    analyzed_text = []
    monkeypatch.setattr(
        resumes_api,
        'analyze_with_gemini',
        lambda text: analyzed_text.append(text) or profile,
    )

    response = client.post(
        '/api/resumes/analyze-text',
        data={'text': 'Python developer with four years of experience.'},
    )

    assert response.status_code == 200
    assert analyzed_text == ['Python developer with four years of experience.']
    assert response.json()['file_name'] == 'Pasted resume text'
    assert response.json()['candidate_name'] == 'Ada Lovelace'
    assert response.json()['rule_based_skills'] == ['Python']
    assert 'stored_file' not in response.json()
    assert 'candidate_id' not in response.json()
    assert client.get('/api/resumes').json() == []

    saved = client.post('/api/resumes/save', data={
        'profile': json.dumps(response.json()),
        'text': 'Python developer with four years of experience.',
    })
    assert saved.status_code == 200
    assert saved.json()['candidate_id']
    assert client.get('/api/resumes').json()[0]['name'] == 'Ada Lovelace'

def test_analyze_duplicate_pasted_resume_does_not_create_another_candidate(client, monkeypatch):
    profile = CandidateProfile(
        candidate_name='Ada Lovelace',
        total_experience_years=4,
        current_role='Python Developer',
        technical_skills=[],
    )
    analyzed_text = []
    monkeypatch.setattr(
        resumes_api,
        'analyze_with_gemini',
        lambda text: analyzed_text.append(text) or profile,
    )
    first = client.post('/api/resumes/analyze-text', data={'text': 'Python Developer\nFour years'})
    assert first.status_code == 200
    assert client.get('/api/resumes').json() == []
    saved = client.post('/api/resumes/save', data={
        'profile': json.dumps(first.json()),
        'text': 'Python Developer\nFour years',
    })
    duplicate = client.post('/api/resumes/analyze-text', data={'text': ' python   developer four YEARS '})

    assert saved.status_code == 200
    assert duplicate.status_code == 200
    assert duplicate.json()['duplicate'] is True
    assert duplicate.json()['candidate_id'] == saved.json()['candidate_id']
    assert len(analyzed_text) == 1
    assert len(client.get('/api/resumes').json()) == 1

def test_uploaded_resume_is_stored_only_after_save_button_action(client, monkeypatch):
    profile = CandidateProfile(
        candidate_name='Ada Lovelace',
        total_experience_years=4,
        current_role='Python Developer',
        technical_skills=[],
    )
    saved_files = []
    monkeypatch.setattr(resumes_api, 'extract_text', lambda _: 'Ada Lovelace Python Developer')
    monkeypatch.setattr(resumes_api, 'analyze_with_gemini', lambda _: profile)
    monkeypatch.setattr(
        resumes_api.storage,
        'put_file',
        lambda key, content, content_type: saved_files.append((key, content, content_type)),
    )
    resume = ('ada.pdf', b'%PDF-1.4 resume bytes', 'application/pdf')
    analyzed = client.post('/api/resumes/analyze', files={'file': resume})

    assert analyzed.status_code == 200
    assert saved_files == []
    assert client.get('/api/resumes').json() == []

    saved = client.post('/api/resumes/save', data={
        'profile': json.dumps(analyzed.json()),
    }, files={'file': resume})

    assert saved.status_code == 200
    assert len(saved_files) == 1
    assert saved.json()['candidate_id']
    assert len(client.get('/api/resumes').json()) == 1


def test_analyze_pasted_resume_text_rejects_empty_text(client, monkeypatch):
    monkeypatch.setattr(
        resumes_api,
        'analyze_with_gemini',
        lambda _: pytest.fail('Gemini should not be called for empty text'),
    )

    response = client.post('/api/resumes/analyze-text', data={'text': '   \n'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'Paste resume text before analyzing.'
