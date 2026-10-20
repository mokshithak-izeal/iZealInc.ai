from fastapi import APIRouter,HTTPException
from pydantic import BaseModel,Field
from app.sources.linkedin_email import extract_linkedin_jobs
from app.workers.job_processor import process_incoming_job
router=APIRouter(prefix='/api/automation',tags=['linkedin-email-ingestion'])
class AlertEmail(BaseModel):
    subject:str='LinkedIn Job Alert'
    body:str
    candidate_profile:dict
    preferred_location:str=''
    threshold:int=Field(80,ge=0,le=100)
@router.post('/linkedin-alert-email')
def ingest(req:AlertEmail):
    incoming=extract_linkedin_jobs(req.subject,req.body)
    if not incoming:raise HTTPException(422,'No LinkedIn /jobs/view/ URL was found in the supplied alert email content.')
    results=[process_incoming_job(x,req.candidate_profile,req.preferred_location,req.threshold) for x in incoming]
    return {'detected':len(incoming),'processed':sum(not x.get('duplicate',False) for x in results),'duplicates':sum(x.get('duplicate',False) for x in results),'results':results}
