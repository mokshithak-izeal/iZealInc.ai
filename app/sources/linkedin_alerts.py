"""LinkedIn job-alert ingestion boundary.
This module intentionally accepts exported/copied alert content rather than automating linkedin.com.
LinkedIn can deliver job alerts by email; feed those alert payloads into parse_alert_payload().
"""
import hashlib
from app.sources.base import IncomingJob

def parse_alert_payload(title:str,job_url:str,description:str)->IncomingJob:
    raw='|'.join([(job_url or '').strip(),(title or '').strip(),(description or '').strip()])
    source_id='linkedin-alert-'+hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]
    return IncomingJob(source_id=source_id,title=(title or '').strip(),job_url=(job_url or '').strip(),description=(description or '').strip())
