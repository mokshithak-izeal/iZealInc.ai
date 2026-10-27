import io
import re
import tempfile
import zipfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from app.agents.job_ai_agent import analyze_job_with_gemini
from app.matching.scorer import score_match
from app.agents.match_ai_agent import analyze_semantic_match
from app.auth import audit, current_user
from app.database.db import session
from app.database.applications import list_applications, save_application
from app.database.jobs import list_jobs,save_analysis,update_status,delete_job,dashboard
from app.database.tables import Candidate, JobDescription
from app.extractors.resume_extractor import extract_text
router=APIRouter(prefix='/api/jobs',tags=['jobs'])
class Match(BaseModel):job_description:str;candidate_profile:dict;preferred_location:str='';threshold:int=80;job_url:str=''
class JobDescriptionInput(BaseModel):
    title: str
    experience: str = ''
    description: str

class SavedMatch(BaseModel):
    candidate_id: str
    job_description_id: str
    preferred_location: str = ''
    threshold: int = Field(default=80, ge=0, le=100)

class Status(BaseModel):status:str
class ApplicationInput(BaseModel):
    title: str
    company: str = ''
    job_url: str = ''
    score: float | None = None
    status: str = 'APPLIED'

MAX_DESCRIPTION_BYTES = 5 * 1024 * 1024
DESCRIPTION_TYPES = {'.txt', '.pdf', '.docx'}
EXPERIENCE_RE = re.compile(
    r'\b\d+(?:\.\d+)?\s*\+?\s*(?:(?:-|\bto\b)\s*\d+(?:\.\d+)?\s*)?(?:years?|yrs?)\b',
    re.I,
)
TITLE_LABEL_RE = re.compile(r'^(?:job\s+title|position|role)\s*:\s*(.+)$', re.I)
GENERIC_TITLE_LINES = {'job description', 'position overview', 'role overview', 'about the role'}

def _description_title(description, filename):
    first_line = next((line.strip() for line in description.splitlines() if line.strip()), '')
    labelled = TITLE_LABEL_RE.match(first_line)
    if labelled:
        return labelled.group(1).strip()[:255]
    if first_line and first_line.lower() not in GENERIC_TITLE_LINES and len(first_line) <= 120:
        return first_line[:255]
    return Path(filename).stem[:255]

def _description_data(row):
    return {
        'id': row.id,
        'title': row.title,
        'experience': row.experience,
        'description': row.description,
        'file': row.original_filename,
        'created_at': row.created_at.isoformat(),
    }

def _normalized_description(description: str) -> str:
    return ' '.join(description.casefold().split())

def _find_duplicate_description(description: str):
    normalized = _normalized_description(description)
    with session() as s:
        rows = s.scalars(select(JobDescription).order_by(JobDescription.created_at)).all()
        return next((row for row in rows
                     if _normalized_description(row.description) == normalized), None)

@router.get('/descriptions')
def list_descriptions(_: dict = Depends(current_user)):
    with session() as s:
        rows = s.scalars(select(JobDescription).order_by(JobDescription.created_at.desc())).all()
        return [_description_data(row) for row in rows]

@router.post('/descriptions')
def create_description(req: JobDescriptionInput, user: dict = Depends(current_user)):
    title = req.title.strip()
    description = req.description.strip()
    if not title:
        raise HTTPException(400, 'Enter a job title.')
    if not description:
        raise HTTPException(400, 'Enter the job description.')
    if len(description.encode('utf-8')) > MAX_DESCRIPTION_BYTES:
        raise HTTPException(413, 'The job description is larger than 5 MB.')
    existing = _find_duplicate_description(description)
    if existing:
        return {**_description_data(existing), 'duplicate': True}
    with session() as s:
        row = JobDescription(title=title[:255], experience=req.experience.strip()[:120],
                             description=description, uploaded_by=user['id'])
        s.add(row)
        s.flush()
        result = _description_data(row)
    audit(user, 'job_description_create', f"{result['id']} {title}")
    return result

@router.post('/descriptions/upload')
async def upload_descriptions(files: list[UploadFile] = File(...),
                              user: dict = Depends(current_user)):
    results = []
    for uploaded in files:
        filename = Path(uploaded.filename or 'job-description').name
        suffix = Path(filename).suffix.lower()
        try:
            if suffix not in DESCRIPTION_TYPES:
                raise HTTPException(400, 'Only TXT, PDF, and DOCX job descriptions are supported.')
            content = await uploaded.read(MAX_DESCRIPTION_BYTES + 1)
            if not content:
                raise HTTPException(400, 'The uploaded job description is empty.')
            if len(content) > MAX_DESCRIPTION_BYTES:
                raise HTTPException(413, 'The job description is larger than 5 MB.')
            if suffix == '.txt':
                description = content.decode('utf-8-sig').strip()
            else:
                if suffix == '.pdf' and not content.startswith(b'%PDF-'):
                    raise HTTPException(400, 'The selected file is not a valid PDF.')
                if suffix == '.docx' and not zipfile.is_zipfile(io.BytesIO(content)):
                    raise HTTPException(400, 'The selected file is not a valid DOCX.')
                with tempfile.TemporaryDirectory() as tmp:
                    path = Path(tmp) / f'description{suffix}'
                    path.write_bytes(content)
                    description = extract_text(path).strip()
            if not description:
                raise HTTPException(400, 'No readable text was found in the job description.')
            existing = _find_duplicate_description(description)
            if existing:
                results.append({'ok': True, 'duplicate': True, **_description_data(existing)})
                continue
            experience_match = EXPERIENCE_RE.search(description)
            experience = experience_match.group(0) if experience_match else ''
            with session() as s:
                row = JobDescription(
                    title=_description_title(description, filename),
                    experience=experience,
                    description=description,
                    original_filename=filename,
                    uploaded_by=user['id'],
                )
                s.add(row)
                s.flush()
                result = _description_data(row)
            audit(user, 'job_description_upload', f"{result['id']} {filename}")
            results.append({'ok': True, **result})
        except HTTPException as exc:
            results.append({'ok': False, 'file': filename, 'error': exc.detail})
        except (UnicodeDecodeError, OSError, ValueError) as exc:
            results.append({'ok': False, 'file': filename, 'error': str(exc)})
        finally:
            await uploaded.close()
    return {'items': results}

@router.post('/match-saved')
def match_saved(req: SavedMatch, user: dict = Depends(current_user)):
    candidate_id = req.candidate_id
    description_id = req.job_description_id
    with session() as s:
        candidate = s.get(Candidate, candidate_id)
        job_description = s.get(JobDescription, description_id)
        if not candidate:
            raise HTTPException(404, 'Candidate not found.')
        if not job_description:
            raise HTTPException(404, 'Job description not found.')
        profile = {key: value for key, value in (candidate.profile or {}).items()
                   if not key.startswith('_')}
        candidate_data = {
            'id': candidate.id,
            'name': candidate.name or 'Unknown candidate',
            'file': candidate.original_filename,
            'experience': profile.get('total_experience_years'),
            'current_role': profile.get('current_role', ''),
        }
        description_data = _description_data(job_description)
    job_input = (
        f"Job title: {description_data['title']}\n"
        f"Required experience: {description_data['experience'] or 'Not specified'}\n\n"
        f"Job description:\n{description_data['description']}"
    )
    job, match, saved_job = _analyze_and_save(
        job_input,
        profile,
        req.preferred_location,
        req.threshold,
        '',
    )
    audit(user, 'candidate_job_match', f"{candidate_id} {description_id}")
    return {
        'candidate': candidate_data,
        'selected_job_description': {
            'id': description_data['id'],
            'title': description_data['title'],
            'experience': description_data['experience'],
        },
        'job': job,
        'match': match,
        'saved_job': saved_job,
    }

def _analyze_and_save(job_description, candidate_profile, preferred_location, threshold, job_url):
    if not job_description.strip():
        raise HTTPException(400, 'Job description is required.')
    try:
        job=analyze_job_with_gemini(job_description).model_dump()
        job.update(source='LinkedIn',job_url=job_url.strip())
        semantic=None
        semantic_error=''
        try:
            semantic=analyze_semantic_match(candidate_profile,job,job_description).model_dump()
        except Exception as exc:
            semantic_error=str(exc)
        match=score_match(candidate_profile,job,preferred_location,threshold,semantic)
        if semantic_error:
            match.setdefault('warnings',[]).append('Gemini semantic matching was unavailable; deterministic skill matching was used for this request.')
        return job, match, save_analysis(job,match)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502,f'Job analysis failed: {e}') from e

@router.post('/analyze-match')
def analyze(req:Match):
    job, match, saved_job = _analyze_and_save(
        req.job_description, req.candidate_profile, req.preferred_location, req.threshold, req.job_url
    )
    return {'job':job,'match':match,'saved_job':saved_job}
@router.get('/queue')
def queue():return list_jobs()
@router.get('/dashboard')
def dash():return dashboard()
@router.get('/applications')
def applications():return list_applications()
@router.post('/mark-applied')
def mark_applied(req: ApplicationInput):
    application = save_application(req.model_dump())
    if application is None:
        raise HTTPException(409, 'This job is already in your applications.')
    return application
@router.patch('/queue/{job_id}/status')
def patch(job_id:str,req:Status):
    try:x=update_status(job_id,req.status)
    except ValueError as e:raise HTTPException(400,str(e)) from e
    if not x:raise HTTPException(404,'Saved job not found.')
    return x
@router.delete('/queue/{job_id}')
def delete(job_id:str):
    if not delete_job(job_id):raise HTTPException(404,'Saved job not found.')
    return {'deleted':True}
