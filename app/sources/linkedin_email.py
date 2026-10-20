import re
from html import unescape
from app.sources.linkedin_alerts import parse_alert_payload

LI_JOB_RE=re.compile(r'https?://(?:www\.)?linkedin\.com/(?:comm/)?jobs/view/[^\s<>"\']+',re.I)

def strip_html(value:str)->str:
    s=re.sub(r'<br\s*/?>','\n',value or '',flags=re.I)
    s=re.sub(r'</(?:p|li|div|h\d)>','\n',s,flags=re.I)
    s=re.sub(r'<[^>]+>',' ',s)
    s=unescape(s)
    s=re.sub(r'[ \t]+',' ',s)
    s=re.sub(r'\n\s*\n+','\n',s)
    return s.strip()

def extract_linkedin_jobs(subject:str,body:str):
    raw=unescape(body or '')
    urls=[]
    for u in LI_JOB_RE.findall(raw):
        u=u.rstrip(').,;\"\'')
        if u not in urls:urls.append(u)
    text=strip_html(raw)
    # Alert emails vary. Preserve the full alert text as evidence/JD input and use subject as title hint.
    jobs=[]
    for i,url in enumerate(urls):
        jobs.append(parse_alert_payload(subject if len(urls)==1 else f'{subject} #{i+1}',url,text))
    return jobs
