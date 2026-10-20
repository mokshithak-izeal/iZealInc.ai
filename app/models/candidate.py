from typing import Optional
from pydantic import BaseModel, Field

class TechnicalSkill(BaseModel):
    name: str = Field(description="Canonical technical skill or technology name")
    confidence: float = Field(ge=0, le=1, description="Confidence that the resume provides evidence for this skill")
    experience_years: Optional[float] = Field(default=None, ge=0, description="Years only when the resume supports this value")
    evidence: str = Field(description="Short evidence paraphrase grounded only in the resume")

class CandidateProfile(BaseModel):
    candidate_name: str = Field(default="", description="Candidate name only if present in the resume")
    total_experience_years: Optional[float] = Field(default=None, ge=0)
    current_role: str = ""
    technical_skills: list[TechnicalSkill] = []
    roles: list[str] = []
    education: list[str] = []
    certifications: list[str] = []
    domains: list[str] = []
