from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI,Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.preferences import router as preferences_router
from app.api.automation import router as automation_router
from app.api.email_ingestion import router as email_ingestion_router
BASE=Path(__file__).resolve().parent;app=FastAPI(title='AI Job Application Agent',version='1.7.1');app.mount('/static',StaticFiles(directory=BASE/'static'),name='static');templates=Jinja2Templates(directory=BASE/'templates');app.include_router(resumes_router);app.include_router(jobs_router);app.include_router(preferences_router);app.include_router(automation_router)
app.include_router(email_ingestion_router)
@app.get('/',response_class=HTMLResponse)
async def home(request:Request):return templates.TemplateResponse(request=request,name='index.html',context={})
@app.get('/api/health')
async def health():return {'status':'healthy','version':'1.7.1','workflow':'resume + preferences + LinkedIn JD matching + queue + tracker + dashboard'}
