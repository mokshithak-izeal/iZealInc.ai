"""Turn a recruiter / vendor requirement email into a job the matcher can use.

These emails carry the job description in the body (no job link), usually followed by
signatures, legal text and Google Groups footers that must not be sent to the AI.
"""
import hashlib
import re
from dataclasses import dataclass
from html import unescape

MAX_CHARS = 15000
THIN_WORDS = 40   # fewer words than this (besides the subject) = title-only email


@dataclass
class IncomingRequirement:
    source_id: str
    title: str
    description: str
    job_url: str = ''
    source: str = 'Recruiter email'
    limited: bool = False


_HTML_HINT = re.compile(r'<\s*(html|body|div|p|br|table|span|td|li)\b', re.I)

# Subscription and legal footers: cut here wherever they appear.
_FOOTERS = [re.compile(p, re.I | re.M) for p in (
    r'you received this message because you are subscribed',
    r'to unsubscribe from this group',
    r'we respect your online privacy',
    r'the material in this e-?mail is intended only',
    r'this e-?mail (?:\(and any attachments\) )?(?:is|may be) (?:confidential|privileged)',
    r'^--[ \t]*$',
)]
# Reply chains: only cut when real content comes before them (forwarded emails start with one).
_CHAINS = [re.compile(p, re.I | re.M) for p in (
    r'^-{3,}\s*original message',
    r'^from:[^\n]+\n(?:sent|date):',
    r'^on [^\n]{8,100} wrote:[ \t]*$',
)]
_SIGNOFF = re.compile(
    r'^[ \t]*(?:thanks\s*(?:&|and)\s*regards|best\s+regards|kind\s+regards|warm\s+regards|'
    r'regards|thanks|thank\s+you)[ \t]*[,.!]?[ \t]*$', re.I | re.M)
_FWD_HEADER = re.compile(r'^\s*(?:-{2,}\s*forwarded message\s*-{2,}|(?:from|to|cc|sent|date|subject)\s*:.*)$', re.I)

_SIGNALS = ('job description', 'responsibilit', 'required skills', 'requirements', 'qualification',
            'years of experience', 'years experience', 'location', 'contract', 'c2c', 'w2', 'full time',
            'full-time', 'onsite', 'on-site', 'remote', 'hybrid', 'duration', 'visa', 'client',
            'position', 'skills', 'experience', 'resume')
_TITLE_WORDS = re.compile(r'\b(developer|engineer|architect|analyst|consultant|administrator|dba|manager|lead|'
                          r'specialist|designer|tester|qa|sdet|devops|sre|scientist|programmer|admin|director|'
                          r'accountant|technician|support)\b', re.I)
_STATE = re.compile(r',\s*[A-Z]{2}\b')


def _html_to_text(raw: str) -> str:
    s = re.sub(r'(?is)<(script|style|head)\b.*?</\1\s*>', ' ', raw)
    s = re.sub(r'(?s)<!--.*?-->', ' ', s)
    s = re.sub(r'(?i)<br\s*/?>', '\n', s)
    s = re.sub(r'(?i)</(p|li|div|tr|h\d)\s*>', '\n', s)
    s = re.sub(r'<[^>]+>', ' ', s)
    return unescape(s)


def clean_requirement_text(raw: str) -> str:
    text = _html_to_text(raw or '') if _HTML_HINT.search(raw or '') else (raw or '')
    text = text.replace('\r', '').replace('\xa0', ' ')
    text = re.sub(r'\[?cid:[^\s\]]+\]?', ' ', text)
    cut = len(text)
    for rx in _FOOTERS:
        m = rx.search(text)
        if m:
            cut = min(cut, m.start())
    for rx in _CHAINS:
        m = rx.search(text)
        if m and len(text[:m.start()].strip()) >= 200:
            cut = min(cut, m.start())
    for m in _SIGNOFF.finditer(text):
        if text[:m.start()].strip():
            cut = min(cut, m.start())
            break
    lines = text[:cut].split('\n')
    head = [ln for ln in lines[:10] if not _FWD_HEADER.match(ln)]   # drop forwarded-message header lines
    text = '\n'.join(head + lines[10:])
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n[ \t]*', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()[:MAX_CHARS]


def clean_subject(subject: str) -> str:
    s = (subject or '').strip()
    s = re.sub(r'^(?:(?:re|fwd?|fw)\s*:\s*)+', '', s, flags=re.I)
    s = re.sub(r'^\s*\[[^\]]{1,80}\]\s*', '', s)
    return s.strip()


def looks_like_requirement(subject: str, text: str) -> bool:
    low = text.lower()
    hits = sum(1 for k in _SIGNALS if k in low)
    return hits >= 3 or bool(_STATE.search(subject)) or bool(_TITLE_WORDS.search(subject))


def extract_requirement(subject: str, body: str, source_key: str) -> list:
    """Returns one IncomingRequirement, or [] when the email is not a job requirement."""
    title = clean_subject(subject)
    text = clean_requirement_text(body)
    if not looks_like_requirement(title, text):
        return []
    limited = len(re.findall(r'\w+', text)) < THIN_WORDS
    return [IncomingRequirement(
        source_id='req:' + hashlib.sha1(source_key.encode()).hexdigest()[:24],
        title=title, description=f'Subject: {title}\n\n{text}'.strip(), limited=limited)]
