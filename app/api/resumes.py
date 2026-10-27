import io
import hashlib
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import ValidationError
from sqlalchemy import select
from app import storage
from app.agents.resume_ai_agent import analyze_with_gemini
from app.auth import admin_only, audit, current_user
from app.database.db import session
from app.database.tables import Candidate, StoredFile
from app.extractors.resume_extractor import extract_skills, extract_text
from app.models.candidate import CandidateProfile

router = APIRouter(prefix='/api/resumes', tags=['resumes'])
MAX_BYTES = 5 * 1024 * 1024
TYPES = {'.pdf': 'application/pdf',
         '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

def _fingerprint(text: str) -> str:
    normalized = ' '.join(text.casefold().split())
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

def _find_duplicate_candidate(text_fingerprint: str, file_fingerprint: str | None = None):
    with session() as s:
        rows = s.execute(
            select(Candidate, StoredFile.data)
            .outerjoin(StoredFile, Candidate.storage_key == StoredFile.key)
            .order_by(Candidate.created_at)
        ).all()
        for row, stored_content in rows:
            profile = row.profile or {}
            if profile.get('_source_fingerprint') == text_fingerprint:
                return row
            if file_fingerprint and profile.get('_file_fingerprint') == file_fingerprint:
                return row
            if file_fingerprint and stored_content is not None:
                if hashlib.sha256(stored_content).hexdigest() == file_fingerprint:
                    return row
    return None

def _candidate_result(row, text: str, duplicate: bool = False):
    profile = row.profile or {}
    years = profile.get('total_experience_years')
    return {
        'file_name': row.original_filename,
        'stored_file': row.storage_key,
        'candidate_id': row.id,
        'duplicate': duplicate,
        'text_extracted': True,
        'extraction_method': 'Gemini structured extraction + deterministic skill signals',
        'rule_based_skills': extract_skills(text),
        'candidate_name': profile.get('candidate_name', row.name),
        'experience': f'{years:g} years' if years is not None else '',
        'current_role': profile.get('current_role', ''),
        'skills': [skill['name'] for skill in profile.get('technical_skills', [])],
        **{key: value for key, value in profile.items()
           if not key.startswith('_')},
    }

def _read_resume(content: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in TYPES:
        raise HTTPException(400, 'Only PDF and DOCX resumes are supported.')
    if not content:
        raise HTTPException(400, 'The uploaded resume is empty.')
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'The resume is larger than 5 MB.')
    if suffix == '.pdf' and not content.startswith(b'%PDF-'):
        raise HTTPException(400, 'The selected file is not a valid PDF.')
    if suffix == '.docx' and not zipfile.is_zipfile(io.BytesIO(content)):
        raise HTTPException(400, 'The selected file is not a valid DOCX. Save it again as .docx in Word, or upload a PDF.')
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f'resume{suffix}'
        path.write_bytes(content)
        resume_text = extract_text(path)
    if not resume_text.strip():
        raise HTTPException(400, 'No readable text was found. The resume may be scanned and require OCR.')
    return resume_text

def _preview(filename: str, resume_text: str, profile: dict):
    years = profile.get('total_experience_years')
    return {
        'file_name': filename,
        'duplicate': False,
        'text_extracted': True,
        'extraction_method': 'Gemini structured extraction + deterministic skill signals',
        'rule_based_skills': extract_skills(resume_text),
        'candidate_name': profile.get('candidate_name', ''),
        'experience': f'{years:g} years' if years is not None else '',
        'current_role': profile.get('current_role', ''),
        'skills': [skill['name'] for skill in profile.get('technical_skills', [])],
        **profile,
    }

@router.post('/analyze')
async def analyze(file: UploadFile = File(...), user: dict = Depends(current_user)):
    original = Path(file.filename or 'resume')
    content = await file.read(MAX_BYTES + 1)
    try:
        text = _read_resume(content, original.name)
        source_fingerprint = _fingerprint(text)
        file_fingerprint = hashlib.sha256(content).hexdigest()
        existing = _find_duplicate_candidate(source_fingerprint, file_fingerprint)
        if existing:
            return _candidate_result(existing, text, duplicate=True)
        profile = analyze_with_gemini(text).model_dump()
        return _preview(original.name, text, profile)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f'AI resume analysis failed: {exc}') from exc

@router.post('/analyze-text')
async def analyze_text(text: str = File(...), user: dict = Depends(current_user)):
    resume_text = text.strip()
    if not resume_text:
        raise HTTPException(400, 'Paste resume text before analyzing.')
    if len(resume_text.encode('utf-8')) > MAX_BYTES:
        raise HTTPException(413, 'The pasted resume is larger than 5 MB.')
    try:
        source_fingerprint = _fingerprint(resume_text)
        existing = _find_duplicate_candidate(source_fingerprint)
        if existing:
            return _candidate_result(existing, resume_text, duplicate=True)
        profile = analyze_with_gemini(resume_text).model_dump()
        return _preview('Pasted resume text', resume_text, profile)
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(502, f'AI resume analysis failed: {exc}') from exc


@router.post('/save')
async def save_candidate(
    profile: str = Form(...),
    file: UploadFile | None = File(None),
    text: str = Form(''),
    user: dict = Depends(current_user),
):
    try:
        candidate_profile = CandidateProfile.model_validate_json(profile).model_dump()
    except ValidationError as exc:
        raise HTTPException(422, 'The analyzed candidate profile is invalid.') from exc

    content = None
    if file is not None:
        filename = Path(file.filename or 'resume').name
        content = await file.read(MAX_BYTES + 1)
        resume_text = _read_resume(content, filename)
        file_fingerprint = hashlib.sha256(content).hexdigest()
    else:
        filename = 'Pasted resume text'
        resume_text = text.strip()
        if not resume_text:
            raise HTTPException(400, 'Resume text is required to save this candidate.')
        if len(resume_text.encode('utf-8')) > MAX_BYTES:
            raise HTTPException(413, 'The pasted resume is larger than 5 MB.')
        file_fingerprint = None

    source_fingerprint = _fingerprint(resume_text)
    existing = _find_duplicate_candidate(source_fingerprint, file_fingerprint)
    if existing:
        return _candidate_result(existing, resume_text, duplicate=True)

    candidate_profile['_source_fingerprint'] = source_fingerprint
    if file_fingerprint:
        candidate_profile['_file_fingerprint'] = file_fingerprint
    key = ''
    if content is not None:
        key = f'resumes/{uuid4().hex}{Path(filename).suffix.lower()}'
        storage.put_file(key, content, TYPES[Path(filename).suffix.lower()])
    with session() as s:
        row = Candidate(
            name=candidate_profile['candidate_name'],
            profile=candidate_profile,
            original_filename=filename,
            storage_key=key,
            uploaded_by=user['id'],
        )
        s.add(row)
        s.flush()
        saved = _candidate_result(row, resume_text)
    audit(user, 'resume_upload' if content is not None else 'resume_text_upload', saved['candidate_id'])
    return saved


@router.get('')
def list_candidates(_: dict = Depends(current_user)):
    with session() as s:
        rows = s.scalars(select(Candidate).order_by(Candidate.created_at.desc())).all()
        return [{
            'id': r.id,
            'name': r.name or 'Unknown candidate',
            'file': r.original_filename,
            'experience': (r.profile or {}).get('total_experience_years'),
            'current_role': (r.profile or {}).get('current_role', ''),
            'profile': {key: value for key, value in (r.profile or {}).items()
                        if not key.startswith('_')},
            'uploaded_by': r.uploaded_by,
            'created_at': r.created_at.isoformat(),
        } for r in rows]

@router.get('/{candidate_id}/download')
def download(candidate_id: str, user: dict = Depends(current_user)):
    with session() as s:
        row = s.get(Candidate, candidate_id)
        if not row:
            raise HTTPException(404, 'Resume not found.')
        key, name = row.storage_key, row.original_filename
    if not key:
        raise HTTPException(404, 'This candidate was created from pasted resume text; no file is available.')
    audit(user, 'resume_download', candidate_id)
    safe = ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)
    return Response(storage.get_file(key), media_type=TYPES.get(Path(key).suffix, 'application/octet-stream'),
                    headers={'Content-Disposition': f'attachment; filename={safe}'})

@router.delete('/{candidate_id}')
def delete_candidate(candidate_id: str, admin: dict = Depends(admin_only)):
    with session() as s:
        row = s.get(Candidate, candidate_id)
        if not row:
            raise HTTPException(404, 'Resume not found.')
        key = row.storage_key
        s.delete(row)
    if key:
        storage.delete_file(key)
    audit(admin, 'resume_delete', candidate_id)
    return {'deleted': True}