import os
from google import genai
from google.genai import types
from app.models.candidate import CandidateProfile
from app.agents.prompts import RESUME_SYSTEM_PROMPT

def analyze_with_gemini(resume_text: str) -> CandidateProfile:
    api_key=os.getenv('GOOGLE_API_KEY')
    if not api_key: raise RuntimeError('GOOGLE_API_KEY is not configured in .env')
    client=genai.Client(api_key=api_key)
    response=client.models.generate_content(
        model=os.getenv('GEMINI_MODEL','gemini-3.8-flash'),
        contents=f"{RESUME_SYSTEM_PROMPT}\n\nRESUME TEXT:\n{resume_text}",
        config=types.GenerateContentConfig(temperature=0,response_mime_type='application/json',response_schema=CandidateProfile),
    )
    return response.parsed if response.parsed is not None else CandidateProfile.model_validate_json(response.text)
