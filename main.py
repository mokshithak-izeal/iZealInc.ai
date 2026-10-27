import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from app.auth import SESSION_TTL_SECONDS, current_user, session_user
from app.database.db import Base, engine
import app.database.tables  # registers the tables
from app.api.auth import router as auth_router
from app.api.resumes import router as resumes_router
from app.api.jobs import router as jobs_router
from app.api.preferences import router as preferences_router
from app.api.automation import router as automation_router
from app.api.email_ingestion import router as email_ingestion_router
from app.api.gmail import router as gmail_router


SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise RuntimeError('SECRET_KEY is missing. Add it to your .env file (see the setup notes).')

BASE = Path(__file__).resolve().parent
Base.metadata.create_all(engine)

app = FastAPI(title='AI Job Application Agent', version='2.0.0',
              docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, max_age=SESSION_TTL_SECONDS, same_site='lax',
                   https_only=os.getenv('COOKIE_SECURE', 'true').lower() == 'true')
app.mount('/static', StaticFiles(directory=BASE / 'static'), name='static')
templates = Jinja2Templates(directory=BASE / 'templates')

# Everything except the sign-in routes requires a signed-in user.
protected = [Depends(current_user)]
app.include_router(auth_router)
for router in (resumes_router, jobs_router, preferences_router, automation_router, email_ingestion_router, gmail_router):
    app.include_router(router, dependencies=protected)


def page(request: Request, name: str):
    return templates.TemplateResponse(request=request, name=name, context={})


@app.get('/login', response_class=HTMLResponse)
async def login_page(request: Request):
    return RedirectResponse('/') if session_user(request) else page(request, 'login.html')


@app.get('/signup', response_class=HTMLResponse)
async def signup_page(request: Request):
    return RedirectResponse('/') if session_user(request) else page(request, 'signup.html')


@app.get('/admin/users', response_class=HTMLResponse)
async def admin_users_page(request: Request):
    user = session_user(request)
    if not user:
        return RedirectResponse('/login')
    if user['role'] != 'admin':
        return RedirectResponse('/')
    return page(request, 'admin_users.html')

@app.get('/account/sessions', response_class=HTMLResponse)
async def account_sessions_page(request: Request):
    if not session_user(request):
        return RedirectResponse('/login')
    return page(request, 'account_sessions.html')


@app.get('/', response_class=HTMLResponse)
async def home(request: Request):
    return page(request, 'index.html') if session_user(request) else RedirectResponse('/login')


@app.get('/api/health')
async def health():
    return {'status': 'healthy', 'version': '2.0.0'}
