import io
import tempfile
import zipfile
from pathlib import Path
from uuid import uuid4
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from app import storage
from app.agents.resume_ai_agent import analyze_with_gemini
from app.auth import admin_only, audit, current_user
from app.database.db import session
from app.database.tables import Candidate
from app.extractors.resume_extractor import extract_skills, extract_text

router = APIRouter(prefix='/api/resumes', tags=['resumes'])
MAX_BYTES = 5 * 1024 * 1024
TYPES = {'.pdf': 'application/pdf',
         '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}

@router.post('/analyze')
async def analyze(file: UploadFile = File(...), user: dict = Depends(current_user)):
    original = Path(file.filename or 'resume')
    suffix = original.suffix.lower()
    if suffix not in TYPES:
        raise HTTPException(400, 'Only PDF and DOCX resumes are supported.')
    content = await file.read()
    if not content:
        raise HTTPException(400, 'The uploaded resume is empty.')
    if len(content) > MAX_BYTES:
        raise HTTPException(413, 'The resume is larger than 5 MB.')
    if suffix == '.pdf' and not content.startswith(b'%PDF-'):
        raise HTTPException(400, 'The selected file is not a valid PDF.')
    if suffix == '.docx' and not zipfile.is_zipfile(io.BytesIO(content)):
        raise HTTPException(400, 'The selected file is not a valid DOCX. Save it again as .docx in Word, or upload a PDF.')
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / f'resume{suffix}'
            path.write_bytes(content)
            text = extract_text(path)
        if not text.strip():
            raise HTTPException(400, 'No readable text was found. The resume may be scanned and require OCR.')
        ai = analyze_with_gemini(text).model_dump()
        key = f'resumes/{uuid4().hex}{suffix}'
        storage.put_file(key, content, TYPES[suffix])
        with session() as s:
            row = Candidate(name=ai['candidate_name'], profile=ai, original_filename=original.name,
                            storage_key=key, uploaded_by=user['id'])
            s.add(row)
            s.flush()
            candidate_id = row.id
        audit(user, 'resume_upload', f'{candidate_id} {original.name}')
        years = ai['total_experience_years']
        return {'file_name': original.name, 'stored_file': key, 'candidate_id': candidate_id,
                'text_extracted': True,
                'extraction_method': 'Gemini structured extraction + deterministic skill signals',
                'rule_based_skills': extract_skills(text),
                'candidate_name': ai['candidate_name'],
                'experience': f'{years:g} years' if years is not None else '',
                'current_role': ai['current_role'],
                'skills': [s['name'] for s in ai['technical_skills']], **ai}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f'AI resume analysis failed: {exc}') from exc

@router.get('')
def list_candidates(_: dict = Depends(current_user)):
    with session() as s:
        rows = s.scalars(select(Candidate).order_by(Candidate.created_at.desc())).all()
        return [{'id': r.id, 'name': r.name, 'file': r.original_filename,
                 'uploaded_by': r.uploaded_by, 'created_at': r.created_at.isoformat()} for r in rows]

@router.get('/{candidate_id}/download')
def download(candidate_id: str, user: dict = Depends(current_user)):
    with session() as s:
        row = s.get(Candidate, candidate_id)
        if not row:
            raise HTTPException(404, 'Resume not found.')
        key, name = row.storage_key, row.original_filename
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
    storage.delete_file(key)
    audit(admin, 'resume_delete', candidate_id)
    return {'deleted': True}