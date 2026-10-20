from fastapi import APIRouter,HTTPException,Form,UploadFile,File
from fastapi.responses import HTMLResponse
from pydantic import BaseModel,Field
from app.sources.linkedin_alerts import parse_alert_payload
from app.workers.job_processor import process_incoming_job
from app.database.automation import history
from app.mock_apply.store import save_submission,submissions
router=APIRouter(tags=['automation-lab'])
class ImportRequest(BaseModel):
    title:str='';job_url:str='';description:str;candidate_profile:dict;preferred_location:str='';threshold:int=Field(80,ge=0,le=100)
@router.post('/api/automation/linkedin-alert')
def linkedin_alert(req:ImportRequest):
    if not req.description.strip():raise HTTPException(400,'description is required')
    incoming=parse_alert_payload(req.title,req.job_url,req.description)
    return process_incoming_job(incoming,req.candidate_profile,req.preferred_location,req.threshold)
@router.get('/api/automation/history')
def automation_history():return history()
@router.get('/mock-apply',response_class=HTMLResponse)
def mock_apply():
    return '''<!doctype html><html><head><title>Mock Easy Apply</title><style>body{font-family:Arial;max-width:700px;margin:40px auto}label{display:block;margin:14px 0}input,select,textarea{width:100%;padding:9px}button{padding:10px 18px}</style></head><body><h1>Mock Job Application</h1><p>Local test portal for JobAgent auto-apply development.</p><form action="/mock-apply/submit" method="post" enctype="multipart/form-data"><label>Full name<input name="full_name" required></label><label>Email<input name="email" type="email" required></label><label>Phone<input name="phone" required></label><label>Years of experience<input name="years_experience" type="number" min="0" required></label><label>Work authorization<select name="work_authorization" required><option value="">Select</option><option>Yes</option><option>No</option></select></label><label>Why are you interested?<textarea name="interest" required></textarea></label><label>Resume<input name="resume" type="file" required></label><button type="submit">Submit Application</button></form></body></html>'''
@router.post('/mock-apply/submit',response_class=HTMLResponse)
async def mock_submit(full_name:str=Form(...),email:str=Form(...),phone:str=Form(...),years_experience:int=Form(...),work_authorization:str=Form(...),interest:str=Form(...),resume:UploadFile=File(...)):
    item=save_submission({'full_name':full_name,'email':email,'phone':phone,'years_experience':years_experience,'work_authorization':work_authorization,'interest':interest,'resume_file':resume.filename})
    return f'''<!doctype html><html><body><h1>Application Submitted</h1><p>Candidate: {item['full_name']}</p><p>Resume: {item['resume_file']}</p><p id="submission-status">SUCCESS</p></body></html>'''
@router.get('/api/mock-apply/submissions')
def mock_submissions():return submissions()
