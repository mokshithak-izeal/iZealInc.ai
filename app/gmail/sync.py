"""Gmail connection, email fetching, and matching each job against every candidate."""
import base64
import hashlib
import os
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from sqlalchemy import select

from app.agents.job_ai_agent import analyze_job_with_gemini
from app.agents.match_ai_agent import analyze_semantic_match
from app.database.automation import record, seen
from app.database.db import session
from app.database.jobs import save_analysis, update_status
from app.database.tables import Candidate, Preference
from app.gmail.models import GmailConnection, GmailMessage, JobMatch
from app.matching.scorer import score_match
from app.sources.linkedin_email import extract_linkedin_jobs
from app.sources.requirement_email import extract_requirement

# Google can return scopes granted earlier; do not fail on that.
os.environ.setdefault('OAUTHLIB_RELAX_TOKEN_SCOPE', '1')

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']
# Only emails matching this search are read. Create a Gmail label named job-requirements (with a filter
# for your requirement mailing list) so no other mail is touched. Override with GMAIL_QUERY if needed.
QUERY = os.getenv('GMAIL_QUERY', 'newer_than:7d (label:job-requirements OR from:linkedin.com)')
MAX_EMAILS = int(os.getenv('GMAIL_MAX_EMAILS', '10'))      # new emails per sync
PREFILTER = float(os.getenv('GMAIL_PREFILTER', '50'))      # skills score needed before the AI comparison
MAX_SEMANTIC = int(os.getenv('GMAIL_MAX_SEMANTIC', '10'))  # AI comparisons per job


# ---------- connection ----------

def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(hashlib.sha256(os.environ['SECRET_KEY'].encode()).digest())
    return Fernet(key)


def configured() -> bool:
    return bool(os.getenv('GOOGLE_CLIENT_ID') and os.getenv('GOOGLE_CLIENT_SECRET'))


def _client_config() -> dict:
    if not configured():
        raise RuntimeError('GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are not set in the environment.')
    return {'web': {'client_id': os.environ['GOOGLE_CLIENT_ID'],
                    'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'}}


def make_flow(redirect_uri: str, state: str | None = None) -> Flow:
    return Flow.from_client_config(_client_config(), scopes=SCOPES, redirect_uri=redirect_uri, state=state)


def finish_connection(creds, user_id: str) -> str:
    svc = build('gmail', 'v1', credentials=creds, cache_discovery=False)
    email = svc.users().getProfile(userId='me').execute().get('emailAddress', '')
    token = _fernet().encrypt(creds.refresh_token.encode()).decode()
    with session() as s:
        row = s.get(GmailConnection, 1) or GmailConnection(id=1)
        row.email, row.refresh_token, row.connected_by = email, token, user_id
        row.connected_at = datetime.now(timezone.utc)
        s.add(row)
    return email


def connection_info() -> dict:
    with session() as s:
        row = s.get(GmailConnection, 1)
        if not row or not row.refresh_token:
            return {'connected': False}
        return {'connected': True, 'email': row.email,
                'connected_at': row.connected_at.isoformat(),
                'last_sync_at': row.last_sync_at.isoformat() if row.last_sync_at else None}


def disconnect():
    with session() as s:
        row = s.get(GmailConnection, 1)
        if row:
            s.delete(row)


def _service():
    with session() as s:
        row = s.get(GmailConnection, 1)
        token = row.refresh_token if row else ''
    if not token:
        raise RuntimeError('Gmail is not connected yet. Connect it first.')
    try:
        refresh = _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise RuntimeError('The stored Gmail connection cannot be read (SECRET_KEY may have changed). '
                           'Disconnect and connect again.') from exc
    cfg = _client_config()['web']
    creds = Credentials(None, refresh_token=refresh, token_uri=cfg['token_uri'],
                        client_id=cfg['client_id'], client_secret=cfg['client_secret'], scopes=SCOPES)
    return build('gmail', 'v1', credentials=creds, cache_discovery=False)


# ---------- reading emails ----------

def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8', 'replace')


def _collect(part: dict, out: dict):
    mime = part.get('mimeType', '')
    data = (part.get('body') or {}).get('data')
    if data and mime in ('text/html', 'text/plain'):
        out[mime] = out.get(mime, '') + _decode(data)
    for sub in part.get('parts') or []:
        _collect(sub, out)


def _subject_and_body(msg: dict):
    payload = msg.get('payload') or {}
    subject = next((h.get('value', '') for h in payload.get('headers', [])
                    if h.get('name', '').lower() == 'subject'), '')
    out: dict = {}
    _collect(payload, out)
    return subject, out.get('text/html') or out.get('text/plain', '')


# ---------- matching ----------

def _name(x) -> str:
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, dict):
        for k in ('skill', 'name', 'requirement', 'required_skill', 'skill_name'):
            if x.get(k):
                return str(x[k]).strip()
    return ''


def _matched_and_missing(parsed: dict, match: dict):
    matched = [_name(x) for x in match.get('required_skill_matches', [])
               if not (isinstance(x, dict) and x.get('matched') is False)]
    matched = [m for m in matched if m]
    have = {m.lower() for m in matched}
    missing = [n for n in (_name(r) for r in parsed.get('required_skills', []))
               if n and n.lower() not in have]
    return matched, missing


def _profile(c: Candidate) -> dict:
    """Rebuild the same profile shape the resume upload screen returns."""
    p = {key: value for key, value in (c.profile or {}).items()
         if not key.startswith('_')}
    p.setdefault('candidate_name', c.name)
    p.setdefault('skills', [s.get('name', '') for s in p.get('technical_skills', []) if isinstance(s, dict)])
    years = p.get('total_experience_years')
    p.setdefault('experience', f'{years:g} years' if years is not None else '')
    p.setdefault('rule_based_skills', [])
    return p


def _context():
    with session() as s:
        cands = [(c.id, c.name, _profile(c)) for c in s.scalars(select(Candidate)).all()]
        pref = s.scalars(select(Preference)).first()
        location = (pref.data or {}).get('preferred_location', '') if pref else ''
    return cands, location, int(os.getenv('MATCH_THRESHOLD', '80'))


def _qualifies(match: dict, threshold: int) -> bool:
    return (match.get('score') is not None and match['score'] >= threshold
            and match.get('decision') != 'NOT_ELIGIBLE')


def _score_of(row) -> float:
    return row[3].get('score') or 0


def _process_job(incoming, cands, location, threshold) -> dict:
    parsed = analyze_job_with_gemini(incoming.description).model_dump()   # one AI call per job
    parsed['source'] = getattr(incoming, 'source', 'LinkedIn Alert')
    limited = bool(getattr(incoming, 'limited', False))
    parsed['job_url'] = incoming.job_url
    # rows: [candidate_id, name, profile, match, used_ai_comparison]
    rows = [[cid, name, prof, score_match(prof, parsed, location, threshold, None), False]
            for cid, name, prof in cands]
    rows.sort(key=_score_of, reverse=True)
    for r in rows[:MAX_SEMANTIC]:        # AI comparison only for the closest candidates
        if _score_of(r) < PREFILTER:
            break
        try:
            sem = analyze_semantic_match(r[2], parsed, incoming.description).model_dump()
            r[3], r[4] = score_match(r[2], parsed, location, threshold, sem), True
        except Exception:
            pass                          # keep the skills-based score
    rows.sort(key=_score_of, reverse=True)
    best = rows[0][3]
    saved = save_analysis(parsed, best)
    target = 'REVIEW' if _qualifies(best, threshold) else 'SKIPPED'
    update_status(saved['id'], target)
    with session() as s:
        for old in s.scalars(select(JobMatch).where(JobMatch.job_id == saved['id'])).all():
            s.delete(old)
        for cid, _who, _prof, m, used_ai in rows:
            matched, missing = _matched_and_missing(parsed, m)
            s.add(JobMatch(job_id=saved['id'], candidate_id=cid, score=m.get('score'),
                           decision=m.get('decision'),
                           status='REVIEW' if _qualifies(m, threshold) else 'BELOW',
                           semantic=used_ai, matched_skills=matched, missing_skills=missing,
                           detail=dict(m, limited_info=limited)))
    record(incoming.source_id, incoming.job_url, parsed.get('title') or incoming.title, target, best.get('score'))
    return {'title': parsed.get('title') or incoming.title, 'best_candidate': rows[0][1],
            'best_score': best.get('score'), 'status': target, 'limited': limited}


def _new_summary() -> dict:
    return {'emails_checked': 0, 'emails_remaining': 0, 'no_jobs_found': 0, 'jobs_found': 0,
            'processed': 0, 'duplicates': 0, 'errors': [], 'results': []}


def _process_email(subject, body, cands, location, threshold, summary, source_key='') -> bool:
    """True when every job in the email was handled (so the email can be marked done)."""
    # LinkedIn alerts first; otherwise treat the email itself as a recruiter requirement.
    jobs = extract_linkedin_jobs(subject, body) or extract_requirement(subject, body, source_key or subject + body)
    if not jobs:
        summary['no_jobs_found'] += 1
        return True
    ok = True
    for inc in jobs:
        summary['jobs_found'] += 1
        if seen(inc.source_id):
            summary['duplicates'] += 1
            continue
        try:
            summary['results'].append(_process_job(inc, cands, location, threshold))
            summary['processed'] += 1
        except Exception as exc:
            ok = False       # leave the email unmarked so the next sync retries it
            summary['errors'].append(f'{inc.job_url or subject}: {str(exc)[:200]}')
    return ok


# ---------- entry points ----------

def run_sync() -> dict:
    cands, location, threshold = _context()
    if not cands:
        raise RuntimeError('Upload at least one resume before syncing.')
    svc = _service()
    listing = svc.users().messages().list(userId='me', q=QUERY, maxResults=50).execute()
    ids = [m['id'] for m in listing.get('messages', [])]
    with session() as s:
        done = set(s.scalars(select(GmailMessage.message_id)
                             .where(GmailMessage.message_id.in_(ids))).all()) if ids else set()
    pending = [i for i in ids if i not in done]
    todo = pending[:MAX_EMAILS]
    summary = _new_summary()
    summary['emails_checked'], summary['emails_remaining'] = len(todo), len(pending) - len(todo)
    for mid in todo:
        msg = svc.users().messages().get(userId='me', id=mid, format='full').execute()
        subject, body = _subject_and_body(msg)
        if _process_email(subject, body, cands, location, threshold, summary, f'gmail:{mid}'):
            with session() as s:
                s.merge(GmailMessage(message_id=mid))
    with session() as s:
        row = s.get(GmailConnection, 1)
        if row:
            row.last_sync_at = datetime.now(timezone.utc)
    return summary


def run_text(subject: str, body: str) -> dict:
    """Same pipeline on a pasted email. Works without any Google connection."""
    cands, location, threshold = _context()
    if not cands:
        raise RuntimeError('Upload at least one resume before testing.')
    summary = _new_summary()
    summary['emails_checked'] = 1
    key = 'paste:' + hashlib.sha1((subject + body).encode()).hexdigest()
    _process_email(subject, body, cands, location, threshold, summary, key)
    return summary
