from typing import Optional
from pydantic import BaseModel, Field

class TechnicalSkill(BaseModel):
    name: str = Field(description="Canonical technical skill or technology name")
    confidence: float = Field(ge=0, le=1, description="Confidence that the resume provides evidence for this skill")
    experience_years: Optional[float] = Field(default=None, ge=0, description="Years only when the resume supports this value")
    evidence: str = Field(description="Short evidence paraphrase grounded only in the resume")


class WorkHistory(BaseModel):
    title: str = ""
    company: str = ""
    start_date: str = ""
    end_date: str = ""
    description: str = ""


class CandidateProfile(BaseModel):
    candidate_name: str = Field(default="", description="Candidate name only if present in the resume")
    email: str = Field(default="", description="Email only when explicitly present in the resume")
    location: str = Field(default="", description="Candidate location only when explicitly present in the resume")
    total_experience_years: Optional[float] = Field(default=None, ge=0)
    current_role: str = ""
    professional_summary: str = Field(default="", description="Concise factual professional summary based only on the resume")
    work_authorization: str = Field(default="", description="Work authorization only when explicitly stated in the resume")
    technical_skills: list[TechnicalSkill] = []
    roles: list[str] = []
    work_history: list[WorkHistory] = []
    education: list[str] = []
    certifications: list[str] = []
    domains: list[str] = []
