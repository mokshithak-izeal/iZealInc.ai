from contextlib import contextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
    select,
)
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.recruiter.router as recruiter_api
from app.auth import current_user
from app.database.db import Base
from app.database.schema_migrations import (
    migrate_legacy_recruiter_data,
    stage_legacy_recruiter_tables,
)
from app.database.tables import Candidate
from app.models.job import JobProfile
from app.recruiter.models import (
    RecruiterCandidate,
    RecruiterIntegration,
    RecruiterJob,
    RecruiterMatch,
    RecruiterSetting,
    RecruiterSubmission,
)


def test_recruiter_workflow_is_persisted_and_scoped(monkeypatch):
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_db_session():
        db = test_session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(recruiter_api, 'session', test_db_session)
    monkeypatch.setattr(recruiter_api, 'audit', lambda *_args: None)
    app = FastAPI()
    app.include_router(recruiter_api.router)
    identity = {'id': 'recruiter-one', 'email': 'one@example.com', 'role': 'recruiter'}
    app.dependency_overrides[current_user] = lambda: identity

    with TestClient(app) as client:
        created_job = client.post('/api/recruiter/jobs', json={
            'title': 'Python Engineer',
            'company': 'Example Inc.',
            'location': 'Remote',
            'employment_type': 'Contract',
            'required_skills': 'Python, FastAPI',
            'minimum_experience_years': 4,
            'external_id': 'REQ-100',
            'description': 'Build and maintain a Python recruiting platform.',
        })
        assert created_job.status_code == 201
        job = created_job.json()
        assert job['required_skills'] == ['Python', 'FastAPI']
        assert job['employment_type'] == 'Contract'
        assert job['external_id'] == 'REQ-100'
        duplicate_job = client.post('/api/recruiter/jobs', json={
            'title': 'Different title',
            'company': 'Different company',
            'description': ' build and maintain a PYTHON recruiting platform. ',
        })
        assert duplicate_job.status_code == 409

        created_candidate = client.post('/api/recruiter/candidates', json={
            'name': 'Casey Candidate',
            'email': 'casey@example.com',
            'location': 'Bengaluru',
            'skills': 'Python, SQL',
            'years_experience': 4,
            'availability': 'Immediate',
            'current_role': 'Python Engineer',
            'profile': {
                'professional_summary': 'Python engineer with four years of experience.',
                'technical_skills': [{'name': 'Python', 'confidence': 0.9, 'experience_years': 4, 'evidence': 'Built APIs'}],
                'roles': ['Python Engineer at Example'],
                'work_history': [{'title': 'Python Engineer', 'company': 'Example'}],
            },
            'work_authorization': 'Authorized to work',
            'notes': 'Follow up next week.',
        })
        assert created_candidate.status_code == 201
        candidate = created_candidate.json()
        assert candidate['location'] == 'Bengaluru'
        assert candidate['availability'] == 'Immediate'
        assert candidate['work_authorization'] == 'Authorized to work'
        assert candidate['notes'] == 'Follow up next week.'
        assert client.get('/api/recruiter/candidates?q=python').json()[0]['id'] == candidate['id']
        candidate_profile = client.get(f"/api/recruiter/candidates/{candidate['id']}")
        assert candidate_profile.status_code == 200
        assert candidate_profile.json()['profile']['professional_summary'].startswith('Python engineer')
        assert candidate_profile.json()['resume_url'] == ''

        updated_profile = client.patch(
            f"/api/recruiter/candidates/{candidate['id']}",
            json={'notes': 'Interview scheduled.', 'work_authorization': 'US work authorized'},
        )
        assert updated_profile.status_code == 200
        assert updated_profile.json()['notes'] == 'Interview scheduled.'
        assert updated_profile.json()['work_authorization'] == 'US work authorized'
        matches = client.post('/api/recruiter/matches/run', json={'job_id': job['id']})
        assert matches.status_code == 200
        assert matches.json()[0]['candidate']['id'] == candidate['id']
        assert matches.json()[0]['score'] == 67
        assert matches.json()[0]['experience_pass'] is True
        match_id = matches.json()[0]['id']
        listed_matches = client.get(f"/api/recruiter/matches/{job['id']}")
        assert listed_matches.status_code == 200
        assert listed_matches.json()[0]['id'] == match_id
        dashboard = client.get('/api/recruiter/dashboard').json()
        assert dashboard['active_jobs'] == 1
        assert dashboard['total_candidates'] == 1
        assert dashboard['matches_found'] == 1

        shortlisted = client.patch(f'/api/recruiter/matches/{match_id}/shortlist')
        assert shortlisted.status_code == 200
        assert shortlisted.json()['shortlisted'] is True
        rerun_matches = client.post('/api/recruiter/matches/run', json={'job_id': job['id']})
        assert rerun_matches.json()[0]['id'] == match_id
        assert rerun_matches.json()[0]['shortlisted'] is True

        missing_consent = client.post('/api/recruiter/submissions', json={
            'job_id': job['id'],
            'candidate_id': candidate['id'],
            'vendor': 'Example Staffing',
            'consent_share': True,
        })
        assert missing_consent.status_code == 400

        submitted = client.post('/api/recruiter/submissions', json={
            'job_id': job['id'],
            'candidate_id': candidate['id'],
            'vendor': 'Example Staffing',
            'consent_share': True,
            'consent_contact': True,
        })
        assert submitted.status_code == 201
        submission_id = submitted.json()['id']

        status = client.patch(
            f'/api/recruiter/submissions/{submission_id}',
            json={'status': 'interview'},
        )
        assert status.status_code == 200
        assert status.json()['status'] == 'interview'
        portal = client.get('/api/recruiter/portal').json()
        assert portal['counts']['interview'] == 1
        assert portal['opportunities'][0]['job']['title'] == 'Python Engineer'

        saved_settings = client.put('/api/recruiter/settings', json={
            'ai_model': 'gemini-test',
            'match_threshold': 60,
        })
        assert saved_settings.status_code == 200
        assert saved_settings.json()['match_threshold'] == 60
        updated_matches = client.post('/api/recruiter/matches/run', json={'job_id': job['id']})
        assert updated_matches.json()[0]['decision'] == 'REVIEW'

        edited_profile = client.patch(
            f"/api/recruiter/candidates/{candidate['id']}",
            json={
                'name': 'Casey Edited',
                'email': 'casey-edited@example.com',
                'location': 'Seattle',
                'years_experience': 6,
                'skills': ['Python', 'FastAPI'],
                'current_role': 'Senior Python Engineer',
                'availability': 'Two weeks',
                'profile': {
                    'professional_summary': 'Updated profile summary.',
                    'technical_skills': [{'name': 'Python'}, {'name': 'FastAPI'}],
                    'work_history': [{'title': 'Senior Python Engineer'}],
                    'education': ['BSc Computer Science'],
                    'certifications': ['AWS Certified Developer'],
                },
            },
        )
        assert edited_profile.status_code == 200
        assert edited_profile.json()['name'] == 'Casey Edited'
        assert edited_profile.json()['email'] == 'casey-edited@example.com'
        assert edited_profile.json()['location'] == 'Seattle'
        assert edited_profile.json()['years_experience'] == 6
        assert edited_profile.json()['skills'] == ['Python', 'FastAPI']
        full_profile = client.get(f"/api/recruiter/candidates/{candidate['id']}").json()
        assert full_profile['profile']['professional_summary'] == 'Updated profile summary.'
        assert full_profile['profile']['education'] == ['BSc Computer Science']

        integration = client.put('/api/recruiter/integrations', json={
            'provider': 'Email',
            'enabled': True,
        })
        assert integration.status_code == 200
        assert next(
            item for item in integration.json()['integrations']
            if item['provider'] == 'Email'
        )['enabled'] is True

        identity.update(id='recruiter-two', email='two@example.com')
        assert client.get('/api/recruiter/jobs').json() == []
        assert client.get('/api/recruiter/candidates').json() == []
        assert client.get(f"/api/recruiter/candidates/{candidate['id']}").status_code == 404
        assert client.delete(f"/api/recruiter/jobs/{job['id']}").status_code == 404
        identity.update(id='recruiter-one', email='one@example.com')
        assert client.delete(f"/api/recruiter/jobs/{job['id']}").status_code == 204


def test_job_description_analysis_returns_gemini_profile_without_saving(monkeypatch):
    engine = create_engine(
        'sqlite://',
        connect_args={'check_same_thread': False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    test_session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_db_session():
        db = test_session()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    monkeypatch.setattr(recruiter_api, 'session', test_db_session)
    profile = JobProfile(
        title='Data Engineer',
        company='Example Inc.',
        location='Remote',
        employment_type='Full Time',
        minimum_experience_years=4,
        required_skills=['Python', 'SQL'],
        preferred_skills=['Spark'],
        responsibilities=['Build data pipelines'],
    )
    analyzed_descriptions = []

    def fake_analyze(description):
        analyzed_descriptions.append(description)
        return profile

    monkeypatch.setattr(recruiter_api, 'analyze_job_with_gemini', fake_analyze)
    app = FastAPI()
    app.include_router(recruiter_api.router)
    app.dependency_overrides[current_user] = lambda: {
        'id': 'recruiter-one',
        'email': 'one@example.com',
        'role': 'recruiter',
    }

    with TestClient(app) as client:
        response = client.post('/api/recruiter/jobs/analyze', json={
            'description': 'A long job description to analyze.',
        })
        assert response.status_code == 200
        assert response.json()['title'] == 'Data Engineer'
        assert response.json()['company'] == 'Example Inc.'
        assert response.json()['required_skills'] == ['Python', 'SQL']
        assert response.json()['preferred_skills'] == ['Spark']
        assert analyzed_descriptions == ['A long job description to analyze.']

        blank_description = client.post('/api/recruiter/jobs/analyze', json={
            'description': '   ',
        })
        assert blank_description.status_code == 400
        assert analyzed_descriptions == ['A long job description to analyze.']
    engine.dispose()


def test_legacy_recruiter_data_migrates_to_new_models():
    engine = create_engine('sqlite://')
    legacy_metadata = MetaData()
    legacy_candidates = Table(
        'candidates',
        legacy_metadata,
        Column('id', String(32), primary_key=True),
        Column('name', String(200)),
        Column('profile', JSON),
        Column('original_filename', String(255)),
        Column('storage_key', String(300)),
        Column('uploaded_by', String(32)),
        Column('created_at', DateTime),
    )
    legacy_jobs = Table(
        'recruiter_jobs',
        legacy_metadata,
        Column('id', String(32), primary_key=True),
        Column('recruiter_id', String(32), nullable=False),
        Column('title', String(255)),
        Column('company', String(255)),
        Column('location', String(255)),
        Column('employment_type', String(50)),
        Column('required_skills', JSON),
        Column('external_id', String(255)),
        Column('minimum_experience_years', Float),
        Column('description', Text),
        Column('source', String(50)),
        Column('status', String(20)),
        Column('created_at', DateTime),
    )
    legacy_matches = Table(
        'recruiter_matches',
        legacy_metadata,
        Column('id', String(32), primary_key=True),
        Column('recruiter_id', String(32), nullable=False),
        Column('job_id', String(32), ForeignKey('recruiter_jobs.id'), nullable=False),
        Column('candidate_id', String(32), ForeignKey('candidates.id'), nullable=False),
        Column('score', Float),
        Column('matched_skills', JSON),
        Column('missing_skills', JSON),
        Column('shortlisted', Integer),
        Column('created_at', DateTime),
        Index('ix_recruiter_matches_job_id', 'job_id'),
        Index('ix_recruiter_matches_candidate_id', 'candidate_id'),
    )
    legacy_submissions = Table(
        'recruiter_submissions',
        legacy_metadata,
        Column('id', String(32), primary_key=True),
        Column('recruiter_id', String(32), nullable=False),
        Column('job_id', String(32), ForeignKey('recruiter_jobs.id'), nullable=False),
        Column('candidate_id', String(32), ForeignKey('candidates.id'), nullable=False),
        Column('vendor', String(255)),
        Column('consent_share', Integer),
        Column('consent_contact', Integer),
        Column('notes', Text),
        Column('status', String(20)),
        Column('created_at', DateTime),
        Index('ix_recruiter_submissions_job_id', 'job_id'),
        Index('ix_recruiter_submissions_candidate_id', 'candidate_id'),
    )
    legacy_settings = Table(
        'recruiter_settings',
        legacy_metadata,
        Column('recruiter_id', String(32), primary_key=True),
        Column('ai_model', String(120)),
        Column('match_threshold', Integer),
        Column('integrations', JSON),
        Column('created_at', DateTime),
    )
    with engine.begin() as connection:
        legacy_metadata.create_all(engine, tables=[
            legacy_candidates, legacy_jobs, legacy_matches, legacy_submissions, legacy_settings,
        ])
        connection.execute(legacy_candidates.insert().values(
            id='old-candidate',
            name='Migrated Candidate',
            profile={
                'email': 'migrated@example.com',
                'location': 'Remote',
                'total_experience_years': 5,
                'current_role': 'Python Engineer',
                'technical_skills': [{'name': 'Python'}, {'name': 'FastAPI'}],
            },
            original_filename='resume.pdf',
            storage_key='',
            uploaded_by='owner-1',
        ))
        connection.execute(legacy_jobs.insert().values(
            id='old-job',
            recruiter_id='owner-1',
            title='Python Engineer',
            company='Example Inc.',
            location='Remote',
            employment_type='Contract',
            required_skills=['Python', 'FastAPI'],
            external_id='REQ-1',
            minimum_experience_years=3,
            description='Build APIs',
            source='Manual',
            status='active',
        ))
        connection.execute(legacy_matches.insert().values(
            id='old-match',
            recruiter_id='owner-1',
            job_id='old-job',
            candidate_id='old-candidate',
            score=90,
            matched_skills=['Python'],
            missing_skills=['FastAPI'],
            shortlisted=True,
        ))
        connection.execute(legacy_submissions.insert().values(
            id='old-submission',
            recruiter_id='owner-1',
            job_id='old-job',
            candidate_id='old-candidate',
            vendor='Example Staffing',
            consent_share=True,
            consent_contact=False,
            notes='Migrated',
            status='submitted',
        ))
        connection.execute(legacy_settings.insert().values(
            recruiter_id='owner-1',
            ai_model='gemini-2.5-flash',
            match_threshold=70,
            integrations=[{'provider': 'Email', 'enabled': True, 'config_json': '{}'}],
        ))

    stage_legacy_recruiter_tables(engine)
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    assert {
        'ix_recruiter_matches_job_id',
        'ix_recruiter_matches_candidate_id',
    }.issubset({index['name'] for index in inspector.get_indexes('legacy_v1_recruiter_matches')})
    assert {
        'ix_recruiter_matches_v2_job_id',
        'ix_recruiter_matches_v2_candidate_id',
    }.issubset({index['name'] for index in inspector.get_indexes('recruiter_matches')})
    assert {
        'ix_recruiter_submissions_job_id',
        'ix_recruiter_submissions_candidate_id',
    }.issubset({index['name'] for index in inspector.get_indexes('legacy_v1_recruiter_submissions')})
    migrate_legacy_recruiter_data(engine)
    with sessionmaker(bind=engine)() as db:
        job = db.scalar(select(RecruiterJob))
        candidate = db.scalar(select(RecruiterCandidate))
        match = db.scalar(select(RecruiterMatch))
        submission = db.scalar(select(RecruiterSubmission))
        setting = db.scalar(select(RecruiterSetting))
        integration = db.scalar(select(RecruiterIntegration))
        assert job.owner_key == 'owner-1'
        assert job.required_skills == 'Python, FastAPI'
        assert job.employment_type == 'Contract'
        assert candidate.email == 'migrated@example.com'
        assert candidate.skills == 'Python, FastAPI'
        assert match.job_id == job.id and match.candidate_id == candidate.id
        assert match.shortlisted is True
        assert submission.vendor == 'Example Staffing'
        assert setting.match_threshold == 70
        assert integration.provider == 'Email' and integration.enabled is True
    assert not any(name.startswith('legacy_v1_') for name in inspect(engine).get_table_names())
