import logging
import os
import time

from google import genai
from google.genai import errors, types

from app.agents.job_postprocess import complete_profile
from app.agents.prompts import JOB_SYSTEM_PROMPT
from app.models.job import JobProfile

log = logging.getLogger('jobagent')

HEADING_RULES = '''
Section headings map as follows:
- Items under "Minimum Qualifications", "Basic Qualifications", "Required Qualifications", "Requirements", "Must Have" or "Key Qualifications" are REQUIRED.
- Items under "Preferred Qualifications", "Nice to Have", "Bonus" or "Desired" are PREFERRED.
Extract every named technology, language, framework, database, platform and engineering methodology in those sections as its own short skill (for example "Python", "FastAPI", "React", "Snowflake"). Split lists such as "Snowflake, Oracle, PostgreSQL, SingleStore" into separate skills. Also extract named technologies that appear in the Responsibilities section.
Fill "responsibilities" with the main duties as short phrases. Fill "minimum_experience_years" from phrases such as "3+ years".
If no job title is stated, give the most fitting short title implied by the description and add a note to extraction_notes saying it was inferred.
'''

RETRY_NOTE = '''

IMPORTANT: a previous attempt returned no skills, but this description does list technologies under its qualification sections. Read it again and list every named skill.
'''


def _generate(client, prompt):
    for attempt in range(3):
        try:
            return client.models.generate_content(
                model=os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type='application/json',
                    response_schema=JobProfile,
                ),
            )
        except errors.APIError as exc:
            if getattr(exc, 'code', None) in (429, 500, 503, 504) and attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise


def _parse(response):
    if response.parsed is not None:
        return response.parsed
    return JobProfile.model_validate_json(response.text)


def _finish_reason(response):
    try:
        return str(response.candidates[0].finish_reason)
    except Exception:
        return 'unknown'


def _has_skills(profile):
    return bool(profile.required_skills or profile.preferred_skills)


def analyze_job_with_gemini(job_text: str) -> JobProfile:
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise RuntimeError('GOOGLE_API_KEY is not configured in .env')
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=90_000))
    prompt = f'{JOB_SYSTEM_PROMPT}\n\n{HEADING_RULES}\n\nJOB DESCRIPTION:\n{job_text}'

    response = _generate(client, prompt)
    profile = _parse(response)
    if not _has_skills(profile) and len(job_text) > 400:
        log.warning('Job parse returned no skills (finish reason: %s); retrying once.', _finish_reason(response))
        response = _generate(client, prompt + RETRY_NOTE)
        profile = _parse(response)
        if not _has_skills(profile):
            log.warning('Retry also returned no skills (finish reason: %s).', _finish_reason(response))
            profile.extraction_notes = list(profile.extraction_notes or []) + [
                f'Gemini returned no skills (finish reason: {_finish_reason(response)}).']

    profile = complete_profile(profile, job_text)

    # A required skill cannot also remain preferred.
    req = {x.strip().lower() for x in profile.required_skills}
    profile.preferred_skills = [x for x in profile.preferred_skills if x.strip().lower() not in req]
    return profile
