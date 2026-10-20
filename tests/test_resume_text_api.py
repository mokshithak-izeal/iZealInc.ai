import pytest
from fastapi.testclient import TestClient

import app.api.resumes as resumes_api
from app.models.candidate import CandidateProfile, TechnicalSkill
from main import app


@pytest.fixture
def client():
    return TestClient(app)


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


def test_analyze_pasted_resume_text_rejects_empty_text(client, monkeypatch):
    monkeypatch.setattr(
        resumes_api,
        'analyze_with_gemini',
        lambda _: pytest.fail('Gemini should not be called for empty text'),
    )

    response = client.post('/api/resumes/analyze-text', data={'text': '   \n'})

    assert response.status_code == 400
    assert response.json()['detail'] == 'Paste resume text before analyzing.'
