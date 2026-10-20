from fastapi import APIRouter,HTTPException
from pydantic import BaseModel
from app.agents.job_ai_agent import analyze_job_with_gemini
from app.matching.scorer import score_match
from app.agents.match_ai_agent import analyze_semantic_match
from app.database.jobs import list_jobs,save_analysis,update_status,delete_job,dashboard
router=APIRouter(prefix='/api/jobs',tags=['jobs'])
class Match(BaseModel):job_description:str;candidate_profile:dict;preferred_location:str='';threshold:int=80;job_url:str=''
class Status(BaseModel):status:str
@router.post('/analyze-match')
def analyze(req:Match):
    if not req.job_description.strip():raise HTTPException(400,'Job description is required.')
    try:
        job=analyze_job_with_gemini(req.job_description).model_dump();job.update(source='LinkedIn',job_url=req.job_url.strip())
        semantic=None
        semantic_error=''
        try:
            semantic=analyze_semantic_match(req.candidate_profile,job,req.job_description).model_dump()
        except Exception as exc:
            # Keep matching usable if the second Gemini call is temporarily unavailable.
            semantic_error=str(exc)
        match=score_match(req.candidate_profile,job,req.preferred_location,req.threshold,semantic)
        if semantic_error:
            match.setdefault('warnings',[]).append('Gemini semantic matching was unavailable; deterministic skill matching was used for this request.')
        return {'job':job,'match':match,'saved_job':save_analysis(job,match)}
    except Exception as e:raise HTTPException(502,f'Job analysis failed: {e}') from e
@router.get('/queue')
def queue():return list_jobs()
@router.get('/dashboard')
def dash():return dashboard()
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
