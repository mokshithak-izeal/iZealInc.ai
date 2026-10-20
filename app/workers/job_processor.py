from app.agents.job_ai_agent import analyze_job_with_gemini
from app.matching.scorer import score_match
from app.agents.match_ai_agent import analyze_semantic_match
from app.database.jobs import save_analysis, update_status
from app.database.automation import seen,record

def process_incoming_job(incoming,candidate_profile,preferred_location='',threshold=80):
    if seen(incoming.source_id):return {'duplicate':True,'source_id':incoming.source_id}
    parsed=analyze_job_with_gemini(incoming.description).model_dump();parsed['source']='LinkedIn Alert';parsed['job_url']=incoming.job_url
    semantic=None
    try:
        semantic=analyze_semantic_match(candidate_profile,parsed,incoming.description).model_dump()
    except Exception:
        # The deterministic scorer remains available if semantic assessment fails.
        semantic=None
    match=score_match(candidate_profile,parsed,preferred_location,threshold,semantic)
    saved=save_analysis(parsed,match)
    target='REVIEW' if match.get('score') is not None and match['score']>=threshold and match.get('decision')!='NOT_ELIGIBLE' else 'SKIPPED'
    update_status(saved['id'],target);record(incoming.source_id,incoming.job_url,parsed.get('title') or incoming.title,target,match.get('score'))
    return {'duplicate':False,'job':parsed,'match':match,'saved_job_id':saved['id'],'auto_status':target}
