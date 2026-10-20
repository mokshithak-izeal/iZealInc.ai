import os
from google import genai
from google.genai import types
from app.models.job import JobProfile
from app.agents.prompts import JOB_SYSTEM_PROMPT

def analyze_job_with_gemini(job_text: str) -> JobProfile:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured in .env")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=f"{JOB_SYSTEM_PROMPT}\n\nJOB DESCRIPTION:\n{job_text}",
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=JobProfile,
        ),
    )
    profile = response.parsed if response.parsed is not None else JobProfile.model_validate_json(response.text)
    # Defensive de-duplication: a required skill cannot also remain preferred.
    req = {x.strip().lower() for x in profile.required_skills}
    profile.preferred_skills = [x for x in profile.preferred_skills if x.strip().lower() not in req]
    return profile
