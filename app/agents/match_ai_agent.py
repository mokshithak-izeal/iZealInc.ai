"""Evidence-grounded semantic resume/JD comparison using Gemini.

The model classifies each skill; the application calculates the final percentage
from those classifications so the LLM cannot invent an arbitrary score.
"""
from __future__ import annotations

import os
import json
from typing import Literal
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.agents.gemini_retry import with_retry


class SkillAssessment(BaseModel):
    job_skill: str = Field(description="The skill exactly as requested by the job")
    status: Literal["exact", "transferable", "partial", "missing"]
    matched_candidate_skills: list[str] = Field(default_factory=list)
    evidence: str = Field(description="Short evidence from the supplied candidate profile only")
    confidence: float = Field(ge=0, le=1)


class SemanticMatchAssessment(BaseModel):
    required_skills: list[SkillAssessment] = Field(default_factory=list)
    preferred_skills: list[SkillAssessment] = Field(default_factory=list)
    role_similarity: float = Field(ge=0, le=1)
    role_evidence: str = ""
    experience_years_supported: float | None = Field(default=None, ge=0)
    experience_evidence: str = ""
    education_match: Literal["match", "partial", "mismatch", "unknown"] = "unknown"
    education_evidence: str = ""
    warnings: list[str] = Field(default_factory=list)


MATCH_SYSTEM_PROMPT = """
You are a careful technical recruiter comparing a candidate profile with a job description.
Return evidence-grounded structured assessments. Use only the supplied candidate profile and job description.

Skill status rules:
- exact: the candidate explicitly lists or demonstrates the same skill or an unambiguous alias.
- transferable: a genuinely adjacent skill gives relevant transferable experience, but is not the same skill.
- partial: some evidence exists, but it is incomplete or weaker than the job requirement.
- missing: no evidence in the supplied profile. Do not assume a skill from a broad job title.

Important distinctions:
- Java is NOT JavaScript. React/Node.js do not prove Java, Spring, or Hibernate.
- SQL can be supported by named SQL databases (e.g. MySQL, PostgreSQL, SQL Server).
- NoSQL can be supported by named NoSQL databases (e.g. MongoDB, Redis).
- Cloud technologies can be supported by explicit Azure, AWS, or GCP experience.
- “Full-stack developer”, “full-stack engineer”, and “full-stack software engineer” are equivalent role-title variants, but a role title alone does not prove every required framework or language.
- Do not treat a related skill as an exact match. Do not invent evidence, dates, years, qualifications, or skills.
- Assess every supplied required and preferred skill once, preserving the job's wording in job_skill.
- Use confidence to express certainty in the classification, not candidate quality.
- Experience must come from the candidate profile's stated experience. If absent, return null; do not calculate from dates unless clearly provided.
- Role similarity is semantic similarity between candidate role/roles/domains and the job title/responsibilities, not a keyword-overlap ratio.
""".strip()


def analyze_semantic_match(candidate_profile: dict, job_profile: dict, job_description: str = "") -> SemanticMatchAssessment:
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not configured in .env")
    client = genai.Client(api_key=api_key)
    payload = {
        "candidate_profile": candidate_profile,
        "job_profile": job_profile,
        "job_description": job_description,
    }
    response = with_retry(lambda: client.models.generate_content(
        model=os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
        contents=f"{MATCH_SYSTEM_PROMPT}\n\nINPUT JSON:\n{json.dumps(payload, ensure_ascii=False, default=str)}",
        config=types.GenerateContentConfig(
            temperature=0,
            response_mime_type="application/json",
            response_schema=SemanticMatchAssessment,
        ),
    ))
    if response.parsed is not None:
        return response.parsed
    return SemanticMatchAssessment.model_validate_json(response.text)
