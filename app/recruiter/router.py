import logging
import re
from datetime import datetime
from json import JSONDecodeError, loads

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError

from app.agents.job_ai_agent import analyze_job_with_gemini
from app.auth import audit, current_user
from app.database.db import session
from app.database.tables import Candidate
from app.database.tables import JobDescription
from app.matching.scorer import score_match
from app.recruiter.models import (
    RecruiterCandidate,
    RecruiterIntegration,
    RecruiterJob,
    RecruiterMatch,
    RecruiterSetting,
    RecruiterSubmission,
)
from app.recruiter.schemas import (
    CandidateIn,
    CandidateProfileUpdateIn,
    IntegrationIn,
    JobDescriptionAnalyzeIn,
    JobIn,
    MatchRunIn,
    SettingsIn,
    SubmissionIn,
    SubmissionStatusIn,
)

router = APIRouter(prefix='/api/recruiter', tags=['Recruiter Suite'])
log = logging.getLogger('jobagent')
SUBMISSION_STATUSES = {'submitted', 'interview', 'offer', 'rejected', 'withdrawn'}
INTEGRATION_PROVIDERS = ('Dice', 'Career Sites', 'Company Portals', 'Email', 'API Integration')


def _skill_list(value: str | list[str]) -> list[str]:
    values = value.replace(';', ',').split(',') if isinstance(value, str) else value
    return list(dict.fromkeys(item.strip() for item in values if item.strip()))


def _normalized_description(value: str) -> str:
    return ' '.join(value.casefold().split())


def _has_duplicate_job_description(db, description: str, owner_key: str) -> bool:
    normalized = _normalized_description(description)
    if not normalized:
        return False
    recruiter_jobs = db.scalars(select(RecruiterJob).where(
        RecruiterJob.owner_key == owner_key,
        RecruiterJob.description != '',
    )).all()
    if any(_normalized_description(job.description) == normalized for job in recruiter_jobs):
        return True
    descriptions = db.scalars(select(JobDescription).where(
        JobDescription.uploaded_by == owner_key,
    )).all()
    return any(_normalized_description(job.description) == normalized for job in descriptions)


def _json_object(value: str) -> dict:
    try:
        result = loads(value)
    except JSONDecodeError as exc:
        raise HTTPException(400, 'Integration config_json must contain valid JSON.') from exc
    if not isinstance(result, dict):
        raise HTTPException(400, 'Integration config_json must be a JSON object.')
    return result


def _candidate_data(row: RecruiterCandidate) -> dict:
    return {
        'id': row.id,
        'name': row.name,
        'email': row.email,
        'location': row.location,
        'skills': _skill_list(row.skills),
        'years_experience': row.years_experience,
        'availability': row.availability,
        'resume_id': row.resume_id,
        'resume_candidate_id': row.resume_candidate_id,
        'current_role': row.current_role,
        'work_authorization': row.work_authorization or '',
        'notes': row.notes or '',
    }


def _job_data(row: RecruiterJob) -> dict:
    return {
        'id': row.id,
        'title': row.title,
        'company': row.company,
        'location': row.location,
        'employment_type': row.employment_type,
        'required_skills': _skill_list(row.required_skills),
        'external_id': row.external_id,
        'minimum_experience_years': row.minimum_experience_years,
        'description': row.description,
        'source': row.source,
        'status': row.status,
        'created_at': row.created_at.isoformat(),
    }


def _submission_data(
    row: RecruiterSubmission,
    candidate: RecruiterCandidate,
    job: RecruiterJob,
) -> dict:
    return {
        'id': row.id,
        'candidate': _candidate_data(candidate),
        'job': _job_data(job),
        'vendor': row.vendor,
        'consent_share': row.consent_share,
        'consent_contact': row.consent_contact,
        'notes': row.notes,
        'status': row.status,
        'created_at': row.created_at.isoformat(),
    }


def _settings_data(row: RecruiterSetting | None, integrations: list | None = None) -> dict:
    by_provider = {item.provider: item for item in (integrations or [])}
    return {
        'ai_model': row.ai_model if row else 'gemini-2.5-flash',
        'match_threshold': row.match_threshold if row else 70,
        'integrations': [
            {
                'provider': provider,
                'enabled': bool(by_provider.get(provider) and by_provider[provider].enabled),
            }
            for provider in INTEGRATION_PROVIDERS
        ],
    }


@router.get('/dashboard')
def dashboard(user: dict = Depends(current_user)):
    owner_key = user['id']
    with session() as db:
        jobs = db.scalars(select(RecruiterJob).where(
            RecruiterJob.owner_key == owner_key,
        )).all()
        active_jobs = [job for job in jobs if job.status == 'active']
        candidates = db.scalars(select(RecruiterCandidate).where(
            RecruiterCandidate.owner_key == owner_key,
        )).all()
        job_ids = [job.id for job in jobs]
        matches = db.scalars(select(RecruiterMatch).where(
            RecruiterMatch.owner_key == owner_key,
            RecruiterMatch.job_id.in_(job_ids) if job_ids else False,
        )).all()
        submissions = db.scalars(select(RecruiterSubmission).where(
            RecruiterSubmission.owner_key == owner_key,
        )).all()
        submission_status = db.execute(
            select(RecruiterSubmission.status, func.count(RecruiterSubmission.id))
            .where(RecruiterSubmission.owner_key == owner_key)
            .group_by(RecruiterSubmission.status)
        ).all()
    return {
        'active_jobs': len(active_jobs),
        'total_candidates': len(candidates),
        'matches_found': len(matches),
        'submissions': len(submissions),
        'recent_jobs': [_job_data(job) for job in sorted(
            active_jobs, key=lambda item: item.created_at, reverse=True
        )[:5]],
        'submission_status': [
            {'status': status_name, 'count': count}
            for status_name, count in submission_status
        ],
    }


@router.post('/jobs/analyze')
def analyze_recruiter_job_description(
    req: JobDescriptionAnalyzeIn,
    user: dict = Depends(current_user),
):
    description = req.description.strip()
    if not description:
        raise HTTPException(400, 'Paste a job description to analyze.')
    with session() as db:
        if _has_duplicate_job_description(db, description, user['id']):
            raise HTTPException(409, 'This job description was already uploaded or saved.')
    try:
        return analyze_job_with_gemini(description).model_dump()
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    except Exception as exc:
        log.exception('Gemini job description analysis failed.')
        raise HTTPException(
            502,
            'Gemini could not analyze this job description. Please try again.',
        ) from exc


@router.get('/jobs')
def list_recruiter_jobs(q: str = '', user: dict = Depends(current_user)):
    with session() as db:
        statement = select(RecruiterJob).where(RecruiterJob.owner_key == user['id'])
        if q.strip():
            pattern = f'%{q.strip()}%'
            statement = statement.where(or_(
                RecruiterJob.title.ilike(pattern),
                RecruiterJob.company.ilike(pattern),
                RecruiterJob.location.ilike(pattern),
                RecruiterJob.required_skills.ilike(pattern),
            ))
        jobs = db.scalars(statement.order_by(RecruiterJob.created_at.desc())).all()
    return [_job_data(job) for job in jobs]


@router.post('/jobs', status_code=status.HTTP_201_CREATED)
def create_recruiter_job(req: JobIn, user: dict = Depends(current_user)):
    title, company = req.title.strip(), req.company.strip()
    if len(title) < 2 or len(company) < 2:
        raise HTTPException(400, 'Job title and company must contain at least two characters.')
    with session() as db:
        if _has_duplicate_job_description(db, req.description, user['id']):
            raise HTTPException(409, 'This job description was already uploaded or saved.')
        job = RecruiterJob(
            owner_key=user['id'],
            title=title,
            company=company,
            location=req.location.strip() or 'Remote',
            employment_type=req.employment_type.strip() or 'Full Time',
            required_skills=', '.join(_skill_list(req.required_skills)),
            external_id=req.external_id.strip() if req.external_id else None,
            minimum_experience_years=req.minimum_experience_years,
            description=req.description.strip(),
            source=req.source.strip() or 'Manual',
        )
        db.add(job)
        db.flush()
        result = _job_data(job)
    audit(user, 'recruiter_job_create', str(result['id']))
    return result


@router.delete('/jobs/{job_id}', status_code=status.HTTP_204_NO_CONTENT)
def delete_recruiter_job(job_id: int, user: dict = Depends(current_user)):
    with session() as db:
        job = db.scalar(select(RecruiterJob).where(
            RecruiterJob.id == job_id,
            RecruiterJob.owner_key == user['id'],
        ))
        if not job:
            raise HTTPException(404, 'Job not found.')
        db.query(RecruiterMatch).filter(
            RecruiterMatch.job_id == job_id,
            RecruiterMatch.owner_key == user['id'],
        ).delete()
        db.query(RecruiterSubmission).filter(
            RecruiterSubmission.job_id == job_id,
            RecruiterSubmission.owner_key == user['id'],
        ).delete()
        db.delete(job)
    audit(user, 'recruiter_job_delete', str(job_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get('/candidates')
def list_recruiter_candidates(q: str = '', user: dict = Depends(current_user)):
    with session() as db:
        statement = select(RecruiterCandidate).where(
            RecruiterCandidate.owner_key == user['id'],
        )
        if q.strip():
            pattern = f'%{q.strip()}%'
            statement = statement.where(or_(
                RecruiterCandidate.name.ilike(pattern),
                RecruiterCandidate.email.ilike(pattern),
                RecruiterCandidate.location.ilike(pattern),
                RecruiterCandidate.skills.ilike(pattern),
                RecruiterCandidate.current_role.ilike(pattern),
            ))
        rows = db.scalars(statement.order_by(RecruiterCandidate.created_at.desc())).all()
    return [_candidate_data(row) for row in rows]


@router.post('/candidates', status_code=status.HTTP_201_CREATED)
def create_recruiter_candidate(req: CandidateIn, user: dict = Depends(current_user)):
    name, email = req.name.strip(), req.email.strip()
    if not name or not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', email):
        raise HTTPException(400, 'Enter a candidate name and valid email address.')
    with session() as db:
        resume = None
        if req.resume_candidate_id:
            resume = db.scalar(select(Candidate).where(
                Candidate.id == req.resume_candidate_id,
                Candidate.uploaded_by == user['id'],
            ))
            if not resume:
                raise HTTPException(404, 'The analyzed resume was not found for this account.')
        profile = {
            key: value for key, value in req.profile.items()
            if not key.startswith('_')
        }
        if resume and not profile:
            profile = {
                key: value for key, value in (resume.profile or {}).items()
                if not key.startswith('_')
            }
        profile_skills = profile.get('technical_skills') or []
        parsed_skills = [
            item.get('name', '') if isinstance(item, dict) else str(item)
            for item in profile_skills
        ]
        skills = ', '.join(_skill_list(req.skills or parsed_skills))
        row = RecruiterCandidate(
            owner_key=user['id'],
            name=name,
            email=email,
            location=req.location.strip(),
            years_experience=req.years_experience,
            skills=skills,
            availability=req.availability.strip() or 'Available',
            resume_id=req.resume_id,
            resume_candidate_id=resume.id if resume else None,
            current_role=req.current_role.strip(),
            profile=profile,
            work_authorization=req.work_authorization.strip() or profile.get('work_authorization', ''),
            notes=req.notes.strip(),
        )
        db.add(row)
        try:
            db.flush()
        except IntegrityError as exc:
            raise HTTPException(409, 'A candidate with this email already exists.') from exc
        result = _candidate_data(row)
    audit(user, 'recruiter_candidate_create', str(result['id']))
    return result


@router.post('/matches/run')
def run_recruiter_match(req: MatchRunIn, user: dict = Depends(current_user)):
    owner_key = user['id']
    with session() as db:
        job = db.scalar(select(RecruiterJob).where(
            RecruiterJob.id == req.job_id,
            RecruiterJob.owner_key == owner_key,
        ))
        if not job:
            raise HTTPException(404, 'Job not found.')
        candidates = db.scalars(select(RecruiterCandidate).where(
            RecruiterCandidate.owner_key == owner_key,
        )).all()
        settings = db.scalar(select(RecruiterSetting).where(
            RecruiterSetting.owner_key == owner_key,
        ))
        threshold = settings.match_threshold if settings else 70
        existing_matches = db.scalars(select(RecruiterMatch).where(
            RecruiterMatch.job_id == job.id,
            RecruiterMatch.owner_key == owner_key,
        )).all()
        matches_by_candidate = {match.candidate_id: match for match in existing_matches}
        candidate_ids = {candidate.id for candidate in candidates}
        for stale_match in existing_matches:
            if stale_match.candidate_id not in candidate_ids:
                db.delete(stale_match)

        results = []
        job_skills = _skill_list(job.required_skills)
        for candidate in candidates:
            candidate_data = _candidate_data(candidate)
            candidate_profile = {
                'current_role': candidate.current_role,
                'total_experience_years': candidate.years_experience,
                'technical_skills': [{'name': skill} for skill in candidate_data['skills']],
            }
            assessment = score_match(
                candidate_profile,
                {
                    'title': job.title,
                    'required_skills': job_skills,
                    'preferred_skills': [],
                    'minimum_experience_years': job.minimum_experience_years,
                    'maximum_experience_years': None,
                },
                threshold=threshold,
            )
            comparisons = assessment['required_skill_matches']
            score = assessment['score'] or 0
            matched_skills = [
                required for required, comparison in zip(job_skills, comparisons)
                if comparison['status'] != 'missing'
            ]
            missing_skills = [
                required for required, comparison in zip(job_skills, comparisons)
                if comparison['status'] == 'missing'
            ]
            match = matches_by_candidate.get(candidate.id)
            if match is None:
                match = RecruiterMatch(
                    owner_key=owner_key,
                    job_id=job.id,
                    candidate_id=candidate.id,
                )
                db.add(match)
            match.score = score
            match.matched_skills = ', '.join(matched_skills)
            match.missing_skills = ', '.join(missing_skills)
            match.explanation = assessment.get('reason') or assessment['decision']
            db.flush()
            results.append({
                'id': match.id,
                'candidate': candidate_data,
                'score': score,
                'matched_skills': match.matched_skills,
                'missing_skills': match.missing_skills,
                'shortlisted': match.shortlisted,
                'experience_pass': assessment['experience_pass'],
                'decision': assessment['decision'],
                'explanation': match.explanation,
            })
        results.sort(key=lambda result: result['score'], reverse=True)
    audit(user, 'recruiter_match_run', str(req.job_id))
    return results


@router.get('/matches/{job_id}')
def list_recruiter_matches(job_id: int, user: dict = Depends(current_user)):
    with session() as db:
        rows = db.execute(
            select(RecruiterMatch, RecruiterCandidate)
            .join(RecruiterCandidate, RecruiterCandidate.id == RecruiterMatch.candidate_id)
            .where(
                RecruiterMatch.owner_key == user['id'],
                RecruiterMatch.job_id == job_id,
                RecruiterCandidate.owner_key == user['id'],
            )
            .order_by(RecruiterMatch.score.desc())
        ).all()
    return [
        {
            'id': match.id,
            'candidate': _candidate_data(candidate),
            'score': match.score,
            'matched_skills': match.matched_skills,
            'missing_skills': match.missing_skills,
            'explanation': match.explanation,
            'shortlisted': match.shortlisted,
        }
        for match, candidate in rows
    ]


@router.patch('/matches/{match_id}/shortlist')
def toggle_shortlist(match_id: int, user: dict = Depends(current_user)):
    with session() as db:
        match = db.scalar(select(RecruiterMatch).where(
            RecruiterMatch.id == match_id,
            RecruiterMatch.owner_key == user['id'],
        ))
        if not match:
            raise HTTPException(404, 'Match not found.')
        match.shortlisted = not match.shortlisted
        result = {'id': match.id, 'shortlisted': match.shortlisted}
    return result


@router.get('/submissions')
def list_submissions(user: dict = Depends(current_user)):
    with session() as db:
        rows = db.execute(
            select(RecruiterSubmission, RecruiterCandidate, RecruiterJob)
            .join(RecruiterCandidate, RecruiterSubmission.candidate_id == RecruiterCandidate.id)
            .join(RecruiterJob, RecruiterSubmission.job_id == RecruiterJob.id)
            .where(RecruiterSubmission.owner_key == user['id'])
            .order_by(RecruiterSubmission.created_at.desc())
        ).all()
    return [
        _submission_data(submission, candidate, job)
        for submission, candidate, job in rows
    ]


@router.post('/submissions', status_code=status.HTTP_201_CREATED)
def create_submission(req: SubmissionIn, user: dict = Depends(current_user)):
    if not req.consent_share or not req.consent_contact:
        raise HTTPException(400, 'Candidate consent to share and direct contact is required.')
    if not req.vendor.strip():
        raise HTTPException(400, 'Vendor is required.')
    owner_key = user['id']
    with session() as db:
        job = db.scalar(select(RecruiterJob).where(
            RecruiterJob.id == req.job_id,
            RecruiterJob.owner_key == owner_key,
        ))
        candidate = db.scalar(select(RecruiterCandidate).where(
            RecruiterCandidate.id == req.candidate_id,
            RecruiterCandidate.owner_key == owner_key,
        ))
        if not job or not candidate:
            raise HTTPException(404, 'Job or candidate not found.')
        row = RecruiterSubmission(
            owner_key=owner_key,
            job_id=job.id,
            candidate_id=candidate.id,
            vendor=req.vendor.strip(),
            consent_share=req.consent_share,
            consent_contact=req.consent_contact,
            notes=req.notes.strip(),
        )
        db.add(row)
        db.flush()
        result = _submission_data(row, candidate, job)
    audit(user, 'recruiter_candidate_submit', str(result['id']))
    return result


@router.patch('/submissions/{submission_id}')
def update_submission_status(
    submission_id: int,
    req: SubmissionStatusIn,
    user: dict = Depends(current_user),
):
    if req.status not in SUBMISSION_STATUSES:
        raise HTTPException(400, 'Unsupported submission status.')
    with session() as db:
        row = db.scalar(select(RecruiterSubmission).where(
            RecruiterSubmission.id == submission_id,
            RecruiterSubmission.owner_key == user['id'],
        ))
        if not row:
            raise HTTPException(404, 'Submission not found.')
        row.status = req.status
        result = {'id': row.id, 'status': row.status}
    return result


@router.get('/portal')
def candidate_portal(user: dict = Depends(current_user)):
    with session() as db:
        rows = db.execute(
            select(RecruiterSubmission, RecruiterCandidate, RecruiterJob)
            .join(RecruiterCandidate, RecruiterSubmission.candidate_id == RecruiterCandidate.id)
            .join(RecruiterJob, RecruiterSubmission.job_id == RecruiterJob.id)
            .where(RecruiterSubmission.owner_key == user['id'])
            .order_by(RecruiterSubmission.created_at.desc())
        ).all()
    opportunities = [
        {
            'job': {
                'title': job.title,
                'company': job.company,
                'location': job.location,
            },
            'status': submission.status,
        }
        for submission, _, job in rows
    ]
    counts = {
        status: sum(submission.status == status for submission, _, _ in rows)
        for status in SUBMISSION_STATUSES
    }
    return {'counts': counts, 'opportunities': opportunities}


@router.get('/settings')
def get_recruiter_settings(user: dict = Depends(current_user)):
    with session() as db:
        settings = db.scalar(select(RecruiterSetting).where(
            RecruiterSetting.owner_key == user['id'],
        ))
        integrations = db.scalars(select(RecruiterIntegration).where(
            RecruiterIntegration.owner_key == user['id'],
        )).all()
        return _settings_data(settings, integrations)


@router.put('/settings')
def save_recruiter_settings(req: SettingsIn, user: dict = Depends(current_user)):
    if not req.ai_model.strip():
        raise HTTPException(400, 'AI model is required.')
    with session() as db:
        row = db.scalar(select(RecruiterSetting).where(
            RecruiterSetting.owner_key == user['id'],
        ))
        if row is None:
            row = RecruiterSetting(owner_key=user['id'])
            db.add(row)
        row.ai_model = req.ai_model.strip()
        row.match_threshold = req.match_threshold
        db.flush()
        integrations = db.scalars(select(RecruiterIntegration).where(
            RecruiterIntegration.owner_key == user['id'],
        )).all()
        result = _settings_data(row, integrations)
    return result


@router.put('/integrations')
def save_integration(req: IntegrationIn, user: dict = Depends(current_user)):
    if req.provider not in INTEGRATION_PROVIDERS:
        raise HTTPException(400, 'Unsupported integration provider.')
    _json_object(req.config_json)
    with session() as db:
        row = db.scalar(select(RecruiterIntegration).where(
            RecruiterIntegration.owner_key == user['id'],
            RecruiterIntegration.provider == req.provider,
        ))
        if row is None:
            row = RecruiterIntegration(
                owner_key=user['id'],
                provider=req.provider,
            )
            db.add(row)
        row.enabled = req.enabled
        row.config_json = req.config_json
        row.last_sync_at = datetime.utcnow() if req.enabled else None
        db.flush()
        settings = db.scalar(select(RecruiterSetting).where(
            RecruiterSetting.owner_key == user['id'],
        ))
        integrations = db.scalars(select(RecruiterIntegration).where(
            RecruiterIntegration.owner_key == user['id'],
        )).all()
        result = _settings_data(settings, integrations)
    return {
        **result,
        'provider': req.provider,
        'enabled': req.enabled,
        'last_sync_at': row.last_sync_at.isoformat() if row.last_sync_at else None,
    }


@router.get('/candidates/{candidate_id}')
def get_recruiter_candidate(candidate_id: int, user: dict = Depends(current_user)):
    with session() as db:
        row = db.scalar(select(RecruiterCandidate).where(
            RecruiterCandidate.id == candidate_id,
            RecruiterCandidate.owner_key == user['id'],
        ))
        if not row:
            raise HTTPException(404, 'Candidate not found.')
        profile = {
            key: value for key, value in (row.profile or {}).items()
            if not key.startswith('_')
        }
        resume = None
        if row.resume_candidate_id:
            resume = db.scalar(select(Candidate).where(
                Candidate.id == row.resume_candidate_id,
                Candidate.uploaded_by == user['id'],
            ))
        result = {
            **_candidate_data(row),
            'profile': profile,
            'resume_file': resume.original_filename if resume else '',
            'resume_url': (
                f'/api/resumes/{resume.id}/view'
                if resume and resume.storage_key
                else ''
            ),
            'created_at': row.created_at.isoformat(),
        }
    return result


@router.patch('/candidates/{candidate_id}')
def update_recruiter_candidate_profile(
    candidate_id: int,
    req: CandidateProfileUpdateIn,
    user: dict = Depends(current_user),
):
    changes = req.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(400, 'Provide at least one candidate detail to update.')
    required_text_fields = (
        'name', 'email', 'location', 'availability', 'current_role',
        'work_authorization', 'notes',
    )
    if any(field in changes and changes[field] is None for field in required_text_fields):
        raise HTTPException(400, 'Candidate text fields cannot be null.')
    if 'email' in changes and not re.fullmatch(r'[^@\s]+@[^@\s]+\.[^@\s]+', changes['email'].strip()):
        raise HTTPException(400, 'Enter a valid email address.')
    if 'name' in changes and not changes['name'].strip():
        raise HTTPException(400, 'Candidate name cannot be empty.')
    with session() as db:
        row = db.scalar(select(RecruiterCandidate).where(
            RecruiterCandidate.id == candidate_id,
            RecruiterCandidate.owner_key == user['id'],
        ))
        if not row:
            raise HTTPException(404, 'Candidate not found.')
        try:
            for field in ('name', 'email', 'location', 'availability', 'current_role', 'notes', 'work_authorization'):
                if field in changes:
                    value = changes[field]
                    setattr(row, field, value.strip() if isinstance(value, str) else value)
            if 'years_experience' in changes:
                row.years_experience = changes['years_experience'] or 0
            if 'skills' in changes:
                row.skills = ', '.join(_skill_list(changes['skills'] or ''))
            if 'profile' in changes:
                row.profile = {
                    key: value for key, value in (changes['profile'] or {}).items()
                    if not key.startswith('_')
                }
            updated_profile = dict(row.profile or {})
            if 'current_role' in changes:
                updated_profile['current_role'] = row.current_role
            if 'location' in changes:
                updated_profile['location'] = row.location
            if 'years_experience' in changes:
                updated_profile['total_experience_years'] = row.years_experience or None
            if 'skills' in changes and 'profile' not in changes:
                updated_profile['technical_skills'] = [
                    {'name': skill} for skill in _skill_list(changes['skills'] or '')
                ]
            if 'work_authorization' in changes:
                updated_profile['work_authorization'] = row.work_authorization
            if any(field in changes for field in ('profile', 'current_role', 'location', 'years_experience', 'skills', 'work_authorization')):
                row.profile = updated_profile
            db.flush()
        except IntegrityError as exc:
            raise HTTPException(409, 'A candidate with this email already exists.') from exc
        result = _candidate_data(row)
    audit(user, 'recruiter_candidate_profile_update', str(candidate_id))
    return result
