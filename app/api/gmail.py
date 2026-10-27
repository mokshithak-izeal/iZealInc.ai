from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import select

from app.auth import admin_only, audit, current_user
from app.database.db import session
from app.database.jobs import list_jobs
from app.database.tables import Candidate
from app.gmail import sync as gmail
from app.gmail.models import JobMatch

router = APIRouter(tags=['gmail'])
templates = Jinja2Templates(directory=Path(__file__).resolve().parents[2] / 'templates')


def _redirect_uri(request: Request) -> str:
    # Built from the address the admin is using, so the sign-in cookie and callback share one host.
    return f'{request.url.scheme}://{request.url.netloc}/auth/google/callback'


@router.get('/gmail', response_class=HTMLResponse)
def gmail_page(request: Request):
    return templates.TemplateResponse(request=request, name='gmail.html', context={})


@router.get('/api/gmail/status')
def status(user: dict = Depends(current_user)):
    return {'accounts': gmail.accounts(), 'is_admin': user['role'] == 'admin'}


@router.get('/auth/google/connect')
def connect(request: Request, org: str = 'izealinc', user: dict = Depends(admin_only)):
    if org not in gmail.ORGS:
        raise HTTPException(400, 'Unknown organization.')
    try:
        flow = gmail.make_flow(org, _redirect_uri(request))
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    url, state = flow.authorization_url(access_type='offline', prompt='consent')
    request.session['gmail_org'] = org
    request.session['gmail_state'] = state
    request.session['gmail_verifier'] = flow.code_verifier
    return RedirectResponse(url)


@router.get('/auth/google/callback')
def callback(request: Request, user: dict = Depends(admin_only)):
    params = request.query_params
    if params.get('error'):
        raise HTTPException(400, f'Google sign-in was not completed ({params["error"]}). Go back and try again.')
    state = request.session.pop('gmail_state', None)
    org = request.session.pop('gmail_org', 'izealinc')
    verifier = request.session.pop('gmail_verifier', None)
    if not state or state != params.get('state') or not params.get('code'):
        raise HTTPException(400, 'The sign-in session expired. Open the Gmail page and click Connect Gmail again.')
    try:
        flow = gmail.make_flow(org, _redirect_uri(request), state=state)
        flow.code_verifier = verifier
        flow.fetch_token(code=params['code'])
        if not flow.credentials.refresh_token:
            raise HTTPException(400, 'Google did not return a long-lived token. Remove "Job Agent" at '
                                     'myaccount.google.com/permissions, then connect again.')
        email = gmail.finish_connection(flow.credentials, user['id'], org)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(502, f'Could not complete the Gmail connection: {exc}') from exc
    audit(user, 'gmail_connect', f'{org} {email}')
    return RedirectResponse('/gmail')


@router.post('/api/gmail/disconnect')
def disconnect(org: str, user: dict = Depends(admin_only)):
    if org not in gmail.ORGS:
        raise HTTPException(400, 'Unknown organization.')
    gmail.disconnect(org)
    audit(user, 'gmail_disconnect', org)
    return {'connected': False}


@router.post('/api/gmail/sync')
def sync_now(user: dict = Depends(admin_only)):
    try:
        summary = gmail.run_sync()
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f'Gmail sync failed: {exc}') from exc
    audit(user, 'gmail_sync', f"{summary['processed']} jobs processed")
    return summary


class PastedEmail(BaseModel):
    subject: str = 'LinkedIn Job Alert'
    body: str


@router.post('/api/gmail/process-text')
def process_text(req: PastedEmail, user: dict = Depends(admin_only)):
    if not req.body.strip():
        raise HTTPException(400, 'Paste the email content first.')
    try:
        summary = gmail.run_text(req.subject, req.body)
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(502, f'Processing failed: {exc}') from exc
    audit(user, 'gmail_test_email', f"{summary['processed']} jobs processed")
    return summary


@router.get('/api/gmail/matches')
def matches(job_id: str = '', _: dict = Depends(current_user)):
    query = select(JobMatch)
    if job_id:
        query = query.where(JobMatch.job_id == job_id)
    query = query.order_by(JobMatch.created_at.desc(), JobMatch.score.desc()).limit(500)
    with session() as s:
        rows = s.scalars(query).all()
        names = {c.id: c.name for c in s.scalars(select(Candidate)).all()}
        data = [{'job_id': r.job_id, 'candidate_id': r.candidate_id, 'score': r.score, 'status': r.status,
                 'ai_checked': r.semantic, 'matched_skills': r.matched_skills,
                 'missing_skills': r.missing_skills, 'created_at': r.created_at.isoformat(),
                 'limited': bool((r.detail or {}).get('limited_info'))} for r in rows]
    jobs = {j['id']: j for j in list_jobs()}
    for d in data:
        job = jobs.get(d['job_id'], {})
        d['candidate'] = names.get(d['candidate_id'], '(deleted)')
        d['title'], d['company'], d['job_url'] = job.get('title', ''), job.get('company', ''), job.get('job_url', '')
    return data
