from pathlib import Path
from uuid import uuid4
import io, zipfile
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from app.extractors.resume_extractor import extract_text, extract_skills
from app.agents.resume_ai_agent import analyze_with_gemini
router=APIRouter(prefix='/api/resumes',tags=['resumes']); BASE_DIR=Path(__file__).resolve().parents[2]; RESUME_DIR=BASE_DIR/'resumes'; RESUME_DIR.mkdir(exist_ok=True)

def _build_profile_response(text:str,file_name:str,stored_file:str|None=None):
    profile=analyze_with_gemini(text); ai=profile.model_dump()
    result={'file_name':file_name,'text_extracted':True,'extraction_method':'Gemini structured extraction + deterministic skill signals','rule_based_skills':extract_skills(text),'candidate_name':ai['candidate_name'],'experience':f"{ai['total_experience_years']:g} years" if ai['total_experience_years'] is not None else '','current_role':ai['current_role'],'skills':[s['name'] for s in ai['technical_skills']],**ai}
    if stored_file is not None: result['stored_file']=stored_file
    return result

@router.post('/analyze')
async def analyze(file:UploadFile=File(...)):
    original=Path(file.filename or 'resume'); suffix=original.suffix.lower()
    if suffix not in {'.pdf','.docx'}: raise HTTPException(400,'Only PDF and DOCX resumes are supported.')
    destination=RESUME_DIR/f'{uuid4().hex}_{original.name}'
    try:
        content=await file.read()
        if not content: raise HTTPException(400,'The uploaded resume is empty.')
        if suffix=='.pdf' and not content.startswith(b'%PDF-'): raise HTTPException(400,'The selected file is not a valid PDF.')
        if suffix=='.docx' and not zipfile.is_zipfile(io.BytesIO(content)): raise HTTPException(400,'The selected file is not a valid DOCX. Open it in Microsoft Word and save it again as .docx, or upload a PDF.')
        destination.write_bytes(content); text=extract_text(destination)
        if not text.strip(): raise HTTPException(400,'No readable text was found. The resume may be scanned and require OCR.')
        return _build_profile_response(text,original.name,destination.name)
    except HTTPException: raise
    except Exception as exc: raise HTTPException(502,f'AI resume analysis failed: {exc}') from exc

@router.post('/analyze-text')
async def analyze_text(text:str=Form(...)):
    if not text.strip(): raise HTTPException(400,'Paste resume text before analyzing.')
    try:
        return _build_profile_response(text,'Pasted resume text')
    except Exception as exc: raise HTTPException(502,f'AI resume analysis failed: {exc}') from exc
