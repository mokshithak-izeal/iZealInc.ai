from pathlib import Path
from datetime import datetime,timezone
from uuid import uuid4
from app.database.state import load_state, save_state, update_state

BASE=Path(__file__).resolve().parents[2];DB=BASE/'data'/'jobs.json'
def load():
    return load_state('jobs',DB,[])
def save(x):save_state('jobs',DB,x)
def list_jobs():return sorted(load(),key=lambda x:x.get('analyzed_at',''),reverse=True)
def save_analysis(job,match):
    url=(job.get('job_url') or '').strip();now=datetime.now(timezone.utc).isoformat()
    def update(rows):
        old=next((x for x in rows if url and x.get('job_url')==url),None)
        item={'id':old.get('id') if old else uuid4().hex,'source':'LinkedIn','job_url':url,'title':job.get('title',''),'company':job.get('company',''),'location':job.get('location',''),'work_mode':job.get('work_mode',''),'required_skills':job.get('required_skills',[]),'preferred_skills':job.get('preferred_skills',[]),'score':match.get('score'),'decision':match.get('decision'),'required_skill_matches':match.get('required_skill_matches',[]),'preferred_skill_matches':match.get('preferred_skill_matches',[]),'experience_pass':match.get('experience_pass'),'score_breakdown':match.get('score_breakdown',{}),'weights_used':match.get('weights_used',{}),'status':old.get('status','NEW') if old else 'NEW','analyzed_at':now}
        if old:rows=[item if x.get('id')==old.get('id') else x for x in rows]
        else:rows.append(item)
        return rows,item
    return update_state('jobs',DB,[],update)
def update_status(i,s):
    if s not in {'NEW','REVIEW','SKIPPED','APPLIED','INTERVIEW','REJECTED','OFFER'}:raise ValueError('Unsupported job status.')
    def update(rows):
        out=None
        for x in rows:
            if x.get('id')==i:x['status']=s;x['status_updated_at']=datetime.now(timezone.utc).isoformat();out=x
        return rows,out
    return update_state('jobs',DB,[],update)
def delete_job(i):
    def update(rows):
        new=[x for x in rows if x.get('id')!=i]
        return new,len(new)!=len(rows)
    return update_state('jobs',DB,[],update)
def dashboard():
    rows=load();scores=[x['score'] for x in rows if isinstance(x.get('score'),(int,float))]
    return {'jobs_analyzed':len(rows),'review':sum(x.get('status')=='REVIEW' for x in rows),'applied':sum(x.get('status')=='APPLIED' for x in rows),'interviews':sum(x.get('status')=='INTERVIEW' for x in rows),'offers':sum(x.get('status')=='OFFER' for x in rows),'skipped':sum(x.get('status')=='SKIPPED' for x in rows),'rejected':sum(x.get('status')=='REJECTED' for x in rows),'average_score':round(sum(scores)/len(scores),1) if scores else None}
