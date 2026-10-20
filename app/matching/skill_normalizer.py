import re

def key(value: str) -> str:
    s=(value or '').strip().lower()
    s=s.replace('&',' and ')
    s=re.sub(r'[^a-z0-9+#./ ]+',' ',s)
    s=re.sub(r'\s+',' ',s).strip()
    return s

ALIASES={
 'python 3.x':'python','python 3':'python','python3':'python',
 'restful api':'rest api','restful apis':'rest api','rest apis':'rest api','restful services':'rest api','rest api':'rest api',
 'microsoft azure':'azure','azure cloud':'azure',
 'postgres':'postgresql','k8s':'kubernetes','mongo':'mongodb',
 'service bus':'azure service bus','microsoft azure service bus':'azure service bus',
 'azure sql':'azure sql database','azure sql db':'azure sql database',
 'key vault':'azure key vault','microsoft azure key vault':'azure key vault',
 'logic app':'azure logic apps','logic apps':'azure logic apps','azure logic app':'azure logic apps',
 'azure function':'azure functions','function app':'azure functions','function apps':'azure functions',
 'git version control':'git',
 'continuous integration continuous deployment':'ci/cd','continuous integration/continuous deployment':'ci/cd',
 'cicd':'ci/cd','ci cd':'ci/cd',
 'cloud monitoring tool':'cloud monitoring tools','cloud security tool':'cloud security tools',
}

RELATED={
 'sql': {'sql server','postgresql','mysql','azure sql database'},
 'nosql': {'mongodb','redis','cosmos db','azure cosmos db'},
 'ci/cd': {'azure devops','github actions','jenkins','azure pipelines'},
 'cloud monitoring tools': {'prometheus','grafana','opentelemetry','azure monitor','application insights'},
 'cloud security tools': {'azure key vault','oauth 2.0','oauth2','managed identity','microsoft entra id'},
 'microservices': {'fastapi','flask','django','docker','kubernetes'},
}

def canonical(value: str) -> str:
    k=key(value)
    return ALIASES.get(k,k)

def classify(job_skill: str, candidate_skills: list[str]) -> dict:
    target=canonical(job_skill)
    candidates=[canonical(x) for x in candidate_skills if x]
    if target in candidates:
        return {'status':'exact','credit':1.0,'matched_with':target}
    for c in candidates:
        if c in RELATED.get(target,set()):
            return {'status':'related','credit':0.5,'matched_with':c}
    for broad,specifics in RELATED.items():
        if target in specifics and broad in candidates:
            return {'status':'related','credit':0.5,'matched_with':broad}
    return {'status':'missing','credit':0.0,'matched_with':''}
