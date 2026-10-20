import re
from app.matching.skill_normalizer import classify

# Weights are normalized over available data, so a missing optional field does
# not automatically penalize a candidate. Required skills remain the largest factor.
WEIGHTS = {'required_skills': 60, 'experience': 20, 'role_similarity': 10, 'preferred_skills': 5, 'education': 5}
SEMANTIC_CREDIT = {'exact': 1.0, 'transferable': 0.65, 'partial': 0.35, 'missing': 0.0}


def token_set(value):
    stop = {'senior', 'junior', 'lead', 'principal', 'software', 'developer', 'engineer', 'engineering', 'backend', 'frontend', 'full', 'stack'}
    return {x for x in re.findall(r'[a-z0-9+#.]+', (value or '').lower()) if len(x) > 2 and x not in stop}


def role_similarity(candidate, job):
    current = candidate.get('current_role') or ''
    title = job.get('title') or ''
    a = token_set(current); b = token_set(title)
    if a and b:
        return len(a & b) / len(b)
    combined = ' '.join((candidate.get('domains') or []) + [x.get('name', '') if isinstance(x, dict) else str(x) for x in candidate.get('technical_skills', [])])
    a = token_set(combined)
    return len(a & b) / len(b) if a and b else 0.0


def rows(skills, candidate_skills):
    return [{'job_skill': s, **classify(s, candidate_skills)} for s in (skills or [])]


def _semantic_rows(skills, semantic_rows, candidate_skills):
    """Use Gemini assessments when available; deterministically fall back per skill."""
    by_key = {str(x.get('job_skill', '')).strip().casefold(): x for x in (semantic_rows or [])}
    result = []
    for skill in skills or []:
        assessment = by_key.get(str(skill).strip().casefold())
        if assessment and assessment.get('status') in SEMANTIC_CREDIT:
            result.append({
                'job_skill': skill,
                'status': assessment['status'],
                'credit': SEMANTIC_CREDIT[assessment['status']],
                'matched_with': ', '.join(assessment.get('matched_candidate_skills') or []),
                'evidence': assessment.get('evidence', ''),
                'confidence': assessment.get('confidence'),
                'match_method': 'gemini_semantic',
            })
        else:
            fallback = classify(skill, candidate_skills)
            result.append({'job_skill': skill, **fallback, 'evidence': '', 'confidence': None, 'match_method': 'rules_fallback'})
    return result


def score_match(candidate, job, preferred_location='', threshold=80, semantic_assessment=None):
    required = job.get('required_skills') or []
    preferred = job.get('preferred_skills') or []
    if not required:
        return {'score': None, 'decision': 'INSUFFICIENT_JOB_DATA', 'reason': 'No required technical skills were extracted from the job description.', 'required_skill_matches': [], 'preferred_skill_matches': [], 'experience_pass': None, 'score_breakdown': {}, 'weights_used': {}}

    cskills = [x.get('name', '') if isinstance(x, dict) else str(x) for x in candidate.get('technical_skills', [])]
    semantic = semantic_assessment or {}
    req = _semantic_rows(required, semantic.get('required_skills'), cskills)
    pref = _semantic_rows(preferred, semantic.get('preferred_skills'), cskills)
    req_ratio = sum(x['credit'] for x in req) / len(req)
    pref_ratio = sum(x['credit'] for x in pref) / len(pref) if pref else None

    cand_exp = candidate.get('total_experience_years')
    # Prefer supported experience parsed by Gemini matching only if profile value is absent.
    if cand_exp is None:
        cand_exp = semantic.get('experience_years_supported')
    min_exp = job.get('minimum_experience_years'); max_exp = job.get('maximum_experience_years')
    exp_specified = min_exp is not None or max_exp is not None
    exp_pass = None
    if exp_specified and cand_exp is not None:
        exp_pass = (min_exp is None or cand_exp >= min_exp) and (max_exp is None or cand_exp <= max_exp)

    role_available = bool(job.get('title'))
    role_score = semantic.get('role_similarity')
    if role_score is None:
        role_score = role_similarity(candidate, job)
    edu_available = bool(job.get('education'))
    education_status = semantic.get('education_match', 'unknown')
    edu_ratio = {'match': 1.0, 'partial': 0.5, 'mismatch': 0.0}.get(education_status)
    if edu_ratio is None:
        # Do not infer a mismatch just because Gemini could not assess it.
        edu_available = False

    available = {
        'required_skills': True,
        'experience': exp_specified and cand_exp is not None,
        'role_similarity': role_available,
        'preferred_skills': bool(preferred),
        'education': edu_available,
    }
    active_weight = sum(WEIGHTS[k] for k, v in available.items() if v)
    def contribution(name, ratio):
        return round((WEIGHTS[name] / active_weight) * ratio * 100, 1) if active_weight else 0

    breakdown = {'required_skills': contribution('required_skills', req_ratio)}
    if available['experience']:
        # Continuous partial credit avoids a binary cliff, but still penalizes shortfalls.
        if min_exp is not None and cand_exp < min_exp:
            exp_ratio = max(0.0, cand_exp / min_exp) if min_exp else 1.0
        elif max_exp is not None and cand_exp > max_exp:
            exp_ratio = max(0.0, max_exp / cand_exp) if cand_exp else 0.0
        else:
            exp_ratio = 1.0
        breakdown['experience'] = contribution('experience', exp_ratio)
    if role_available:
        breakdown['role_similarity'] = contribution('role_similarity', max(0.0, min(1.0, float(role_score))))
    if preferred:
        breakdown['preferred_skills'] = contribution('preferred_skills', pref_ratio)
    if edu_available:
        breakdown['education'] = contribution('education', edu_ratio)

    score = max(0, min(100, round(sum(breakdown.values()))))
    decision = 'NOT_ELIGIBLE' if exp_pass is False else ('REVIEW' if score >= threshold else 'BELOW_THRESHOLD')
    weights_used = {k: round(WEIGHTS[k] / active_weight * 100, 1) for k, v in available.items() if v}
    return {
        'score': score, 'decision': decision, 'reason': '',
        'required_skill_matches': req, 'preferred_skill_matches': pref,
        'experience_pass': exp_pass, 'candidate_experience_years': cand_exp,
        'experience_evidence': semantic.get('experience_evidence', ''),
        'role_evidence': semantic.get('role_evidence', ''),
        'education_match': education_status, 'education_evidence': semantic.get('education_evidence', ''),
        'warnings': semantic.get('warnings', []),
        'score_breakdown': breakdown, 'weights_used': weights_used, 'threshold': threshold,
        'matching_method': 'gemini_semantic_hybrid' if semantic_assessment else 'rules_only',
    }
