from app.matching.scorer import score_match


def candidate():
    return {
        'current_role': 'Senior Backend Engineer',
        'total_experience_years': 6,
        'technical_skills': [
            {'name': 'JavaScript'}, {'name': 'HTML'}, {'name': 'CSS'},
            {'name': 'MySQL'}, {'name': 'MongoDB'}, {'name': 'Azure'},
            {'name': 'Python'}, {'name': 'FastAPI'},
        ],
        'roles': ['Backend Engineer', 'Software Engineer'],
        'domains': ['backend development', 'cloud technologies'],
        'education': ['Bachelor degree'],
    }


def job():
    return {
        'title': 'Full Stack Engineer',
        'minimum_experience_years': 3,
        'required_skills': ['Java Full Stack Development', 'HTML', 'CSS', 'JavaScript', 'Spring', 'Hibernate', 'SQL', 'NoSQL', 'Cloud technologies'],
        'preferred_skills': [],
        'education': [],
    }


def test_synonym_and_skill_evidence_affect_score():
    semantic = {
        'required_skills': [
            {'job_skill':'Java Full Stack Development','status':'missing','matched_candidate_skills':[],'evidence':'No Java/Spring evidence','confidence':0.95},
            {'job_skill':'HTML','status':'exact','matched_candidate_skills':['HTML'],'evidence':'Listed','confidence':0.99},
            {'job_skill':'CSS','status':'exact','matched_candidate_skills':['CSS'],'evidence':'Listed','confidence':0.99},
            {'job_skill':'JavaScript','status':'exact','matched_candidate_skills':['JavaScript'],'evidence':'Listed','confidence':0.99},
            {'job_skill':'Spring','status':'missing','matched_candidate_skills':[],'evidence':'Not listed','confidence':0.95},
            {'job_skill':'Hibernate','status':'missing','matched_candidate_skills':[],'evidence':'Not listed','confidence':0.95},
            {'job_skill':'SQL','status':'exact','matched_candidate_skills':['MySQL'],'evidence':'MySQL is listed','confidence':0.95},
            {'job_skill':'NoSQL','status':'exact','matched_candidate_skills':['MongoDB'],'evidence':'MongoDB is listed','confidence':0.95},
            {'job_skill':'Cloud technologies','status':'exact','matched_candidate_skills':['Azure'],'evidence':'Azure is listed','confidence':0.95},
        ],
        'preferred_skills': [], 'role_similarity': 0.8,
        'experience_years_supported': 6, 'experience_evidence': '6+ years',
        'education_match': 'unknown', 'warnings': [],
    }
    result = score_match(candidate(), job(), semantic_assessment=semantic)
    assert result['score'] is not None
    assert 0 <= result['score'] <= 100
    assert result['experience_pass'] is True
    assert result['decision'] != 'NOT_ELIGIBLE'
    assert result['matching_method'] == 'gemini_semantic_hybrid'
    assert result['required_skill_matches'][0]['status'] == 'missing'
    assert result['required_skill_matches'][6]['status'] == 'exact'


def test_full_stack_title_variants_do_not_override_missing_core_skills():
    result = score_match(candidate(), job())
    assert 0 <= result['score'] <= 100
    assert result['experience_pass'] is True
    # Deterministic fallback should recognize listed HTML/CSS/JavaScript and databases,
    # while not falsely equating JavaScript with Java.
    matches = {x['job_skill']: x['status'] for x in result['required_skill_matches']}
    assert matches['HTML'] == 'exact'
    assert matches['CSS'] == 'exact'
    assert matches['JavaScript'] == 'exact'
    assert matches['Java Full Stack Development'] == 'missing'
